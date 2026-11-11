from __future__ import annotations

import os
import re
import math
import functools
import shlex
import subprocess
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

import numpy as np

from utils import os_helpers
from utils.logger import Logger


class DetectorError(Exception):
    """An error that makes the whole run impossible (bad snippet, bad options)."""


# Audio is analysed as a log-mel spectrogram: 16 kHz mono, 64 ms frames every 10 ms, 40 bands from 100 Hz to 7 kHz.
SAMPLE_RATE = 16000
N_FFT = 1024
HOP = 160
FRAME_RATE = SAMPLE_RATE / HOP
N_BANDS = 40
F_MIN, F_MAX = 100.0, 7000.0
POWER_FLOOR = 1e-2  # about -68 dB below a full-scale sine; quieter content is treated as silence

# Speed changes found in real releases: PAL speed-up (23.976/24 fps film played at 25 fps) and the reverse.
# Each is tried with the pitch shifted along (plain speed-up) and with the pitch corrected.
SPEED_FACTORS = (25 / 24, 25 / 23.976, 24 / 25, 23.976 / 25)


def _mel(f):
    return 2595.0 * np.log10(1.0 + f / 700.0)


def _mel_to_hz(m):
    return 700.0 * (10.0 ** (m / 2595.0) - 1.0)


def _filterbank(pitch=1.0):
    """
    Triangular mel filters, shape (bins, bands). With pitch != 1 the filters are moved to where the content of
    each band would be before a pitch shift by that factor, so a shifted snippet still lines up with the episode.
    """
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / SAMPLE_RATE)
    edges = _mel_to_hz(np.linspace(_mel(F_MIN), _mel(F_MAX), N_BANDS + 2)) / pitch
    bank = np.zeros((len(freqs), N_BANDS))
    for b in range(N_BANDS):
        lo, center, hi = edges[b], edges[b + 1], edges[b + 2]
        rising = (freqs - lo) / (center - lo)
        falling = (hi - freqs) / (hi - center)
        bank[:, b] = np.maximum(0.0, np.minimum(rising, falling))
    return bank


def power_spectrogram(audio):
    """Power spectrogram, shape (frames, bins)."""
    if len(audio) < N_FFT:
        audio = np.pad(audio, (0, N_FFT - len(audio)))
    frames = np.lib.stride_tricks.sliding_window_view(audio, N_FFT)[::HOP]
    window = np.hanning(N_FFT).astype(np.float32)
    out = np.empty((len(frames), N_FFT // 2 + 1), dtype=np.float32)
    for i in range(0, len(frames), 4096):  # chunked to keep memory flat for long windows
        spectrum = np.fft.rfft(frames[i:i + 4096] * window, axis=1)
        out[i:i + 4096] = spectrum.real ** 2 + spectrum.imag ** 2
    return out


@functools.lru_cache(maxsize=16)
def _cached_filterbank(pitch):
    return _filterbank(pitch).astype(np.float32)


def log_bands(power, pitch=1.0):
    return np.log10(power @ _cached_filterbank(pitch) + POWER_FLOOR)


def snippet_variants(power, speed_search=True):
    """
    The snippet's features as they would appear in an episode at each tried speed: list of (speed, features).
    Features are zero-mean per band, which makes the match ignore volume and EQ (constant per-band offsets in the
    log domain).
    """
    combos = [(1.0, 1.0)]
    if speed_search:
        for factor in SPEED_FACTORS:
            combos += [(factor, factor), (factor, 1.0)]

    variants = []
    for speed, pitch in combos:
        features = log_bands(power, pitch)
        frames = max(2, round(len(features) / speed))
        if frames != len(features):
            positions = np.linspace(0, len(features) - 1, frames)
            features = np.stack([np.interp(positions, np.arange(len(features)), band) for band in features.T], axis=1)
        features = features - features.mean(axis=0)
        variants.append((speed, features))
    return variants


class Episode:
    """An episode's features, prepared once so that every snippet variant can be matched against it cheaply."""

    def __init__(self, features):
        self.frames = len(features)
        self.fft_size = 1 << (self.frames - 1).bit_length()
        bands = np.ascontiguousarray(features.T)  # (bands, frames): FFT along contiguous memory
        self.spectrum = np.fft.rfft(bands, self.fft_size, axis=1)
        zero = np.zeros((bands.shape[0], 1))
        self.sums = np.concatenate((zero, np.cumsum(bands, axis=1)), axis=1)
        self.squares = np.concatenate((zero, np.cumsum(bands * bands, axis=1)), axis=1)


def match_features(episode: Episode, snippet, snippet_spectrum=None):
    """
    Normalised cross-correlation of the snippet over the episode, summed over all bands, with the episode's mean
    removed per band and position. Returns an array with one score in [-1, 1] per possible start frame.
    """
    n = len(snippet)
    if snippet_spectrum is None:
        snippet_spectrum = np.fft.rfft(np.ascontiguousarray(snippet.T), episode.fft_size, axis=1)
    cross = (episode.spectrum * np.conj(snippet_spectrum)).sum(axis=0)
    numerator = np.fft.irfft(cross, episode.fft_size)[:episode.frames - n + 1]

    window_sum = episode.sums[:, n:] - episode.sums[:, :-n]
    window_squares = episode.squares[:, n:] - episode.squares[:, :-n]
    variance = np.maximum(window_squares - window_sum * window_sum / n, 0.0).sum(axis=0)

    denominator = np.sqrt(variance * float((snippet * snippet).sum()))
    scores = np.zeros_like(numerator)
    np.divide(numerator, denominator, out=scores, where=denominator > 1e-9)
    return np.minimum(scores, 1.0)


# Set once per worker process by _init_worker, so the snippet isn't sent along with every job.
_variants = None
_variant_spectra = {}  # fft size -> FFT of every variant; most episodes share one size


def _init_worker(variants):
    global _variants
    _variants = variants
    _variant_spectra.clear()


def _match(audio):
    """Best (frame, score, speed) for one episode, or raises ValueError if it is too short."""
    episode = Episode(log_bands(power_spectrogram(audio)).astype(np.float64))
    if episode.fft_size not in _variant_spectra:
        _variant_spectra[episode.fft_size] = [np.fft.rfft(np.ascontiguousarray(snippet.T), episode.fft_size, axis=1)
                                              for _, snippet in _variants]
    best = None
    for (speed, snippet), snippet_spectrum in zip(_variants, _variant_spectra[episode.fft_size]):
        if len(snippet) > episode.frames:
            continue
        scores = match_features(episode, snippet, snippet_spectrum)
        frame = int(np.argmax(scores))
        if best is None or scores[frame] > best[1]:
            best = (frame, float(scores[frame]), speed)
    if best is None:
        raise ValueError(f"only {len(audio) / SAMPLE_RATE:.2f}s of audio, shorter than the base file")
    return best


class Detector:
    def __init__(self, base_file: str, files: list[str], time_: int, window: int, ffmpeg: str, logger: Logger,
                 aivd_threads=1, ffmpeg_processes=1, ffmpeg_args: str | None = None, min_score=0.5,
                 strict_window=False, from_end=False, speed_search=True, base_data: bytes | None = None,
                 on_result=None):
        self._base_file = base_file
        self._base_data = base_data
        self._base_name = "stdin" if base_data is not None else f"'{base_file}'"
        self._on_result = on_result
        self._files = files
        self._threads = aivd_threads
        self._ffmpeg_processes = ffmpeg_processes
        self._ffmpeg_args = shlex.split(ffmpeg_args) if ffmpeg_args else []

        self.time = time_
        self.window = window
        self.ffmpeg = ffmpeg
        self.logger = logger
        self.min_score = min_score
        self.strict_window = strict_window
        self.from_end = from_end
        self.speed_search = speed_search

        self._variants = None

    def _run_ffmpeg(self, input_options, file, stdin_data=None, pass_fds=()):
        """Decode `file` to mono float32 at SAMPLE_RATE. With `stdin_data`, `file` should be "pipe:0"."""
        command = [
            self.ffmpeg, *([] if stdin_data is not None else ["-nostdin"]), "-hide_banner", "-loglevel", "error",
            *input_options, "-i", file,
            "-vn", "-sn", "-dn",
            *self._ffmpeg_args,
            "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1",
        ]
        self.logger.debug(f"\tDecoding '{file}': {shlex.join(command)}")

        stdin = {"input": stdin_data} if stdin_data is not None else {"stdin": subprocess.DEVNULL}
        result = subprocess.run(command, capture_output=True, pass_fds=pass_fds, env=os_helpers.subprocess_env(),
                                **stdin)
        if result.returncode != 0:
            lines = result.stderr.decode("utf-8", errors="replace").strip().splitlines()
            message = " / ".join(line.strip() for line in lines if line.strip()) or f"exit code {result.returncode}"
            raise RuntimeError(f"ffmpeg failed: {message}")
        return np.frombuffer(result.stdout, dtype="<f4")

    def _duration(self, file):
        """Container duration in seconds, as ffmpeg's -sseof sees it."""
        result = subprocess.run([self.ffmpeg, "-nostdin", "-hide_banner", "-i", file], capture_output=True,
                                stdin=subprocess.DEVNULL, env=os_helpers.subprocess_env())
        found = re.search(rb"Duration: (\d+):(\d\d):(\d\d(?:\.\d+)?)", result.stderr)
        if found is None:
            raise RuntimeError("could not determine the duration, which --from-end needs")
        hours, minutes, seconds = found.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    def _decode_buffer(self, input_options, data):
        """
        Decode audio held in memory. ffmpeg can't seek in a pipe, which some formats need (mp4/m4a with the index at
        the end of the file), so on Linux the data goes into an anonymous in-memory file (memfd) that ffmpeg opens
        via /dev/fd. Nothing is written to disk either way.
        """
        if not hasattr(os, "memfd_create"):
            hint = ("on this platform the input is read from a pipe, and mp4/m4a files need their index at the start "
                    "for that: ffmpeg -i in.m4a -c copy -movflags +faststart out.m4a")
            try:
                audio = self._run_ffmpeg(input_options, "pipe:0", stdin_data=data)
            except RuntimeError as e:
                raise RuntimeError(f"{e} ({hint})") from e
            if len(audio) == 0:  # ffmpeg can exit successfully on such a file without decoding anything
                raise RuntimeError(f"no audio could be decoded ({hint})")
            return audio

        fd = os.memfd_create("aivd-input")
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            return self._run_ffmpeg(input_options, f"/dev/fd/{fd}", pass_fds=(fd,))
        finally:
            os.close(fd)

    def _load_snippet(self):
        self.logger.info("Loading base file...")
        input_options = ["-t", str(self.time)] if self.time > 0 else []
        try:
            if self._base_data is None:
                audio = self._run_ffmpeg(input_options, self._base_file)
            else:
                audio = self._decode_buffer(input_options, self._base_data)
        except RuntimeError as e:
            raise DetectorError(f"Could not load base file from {self._base_name}: {e}") from e

        length = len(audio) / SAMPLE_RATE
        if length < 1:
            raise DetectorError(f"Base file from {self._base_name} must contain at least 1 second of audio.")
        if not np.any(audio):
            raise DetectorError(f"Base file from {self._base_name} is silent.")
        self.logger.debug(f"\tBase file: {length:.2f}s.")

        self._variants = snippet_variants(power_spectrogram(audio), self.speed_search)
        self.logger.debug(f"\tMatching at speeds: {', '.join(f'{speed:.4f}' for speed in sorted({s for s, _ in self._variants}))}.")

        if self.window <= length:
            if self.strict_window:
                raise DetectorError(f"The window ({self.window}s) must be longer than the base file "
                                    f"({length:.2f}s). Increase --window or shorten the base file with --time.")
            new_window = math.ceil(length) + self.window
            self.logger.warning(f"The window ({self.window}s) is shorter than the base file ({length:.2f}s). "
                                f"Extending it to {new_window}s so the base file can start anywhere in the "
                                f"{'last' if self.from_end else 'first'} {self.window}s. "
                                f"Use --strict-window to make this an error instead.")
            self.window = new_window
        self.logger.empty_line()

    def _decode(self, file):
        """Returns (audio of the searched part, its start time in the file in seconds)."""
        if not self.from_end:
            return self._run_ffmpeg(["-t", str(self.window)], file), 0.0

        duration = self._duration(file)
        start = max(0.0, duration - self.window)
        return self._run_ffmpeg(["-ss", f"{start:.3f}"], file), start

    def _result(self, frame=None, score=None, speed=None, start=0.0, error=None):
        if error is not None:
            return {"offset": None, "score": None, "speed": None, "found": False, "error": error}
        return {
            "offset": round(start + frame / FRAME_RATE, 2),
            "score": round(score, 3),
            "speed": round(speed, 4),
            "found": score >= self.min_score,
            "error": None,
        }

    def _finished(self, results, file, result):
        results[file] = result
        if self._on_result is not None:
            self._on_result(file, result)

    def _detect(self):
        self.logger.info(f"Searching {len(self._files)} files...")
        self.logger.debug(f"\tUsing {self._ffmpeg_processes} ffmpeg processes and {self._threads} detector processes.")
        results = {}

        # The work is already spread over processes; numpy's BLAS starting one thread per CPU in each of them only
        # makes them compete. Spawned workers inherit this environment before they import numpy.
        for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ.setdefault(variable, "1")

        # "spawn": the process pool is started while decoder threads are running, and forking a multi-threaded
        # process can deadlock.
        with ThreadPoolExecutor(max_workers=self._ffmpeg_processes) as decoders, \
                ProcessPoolExecutor(max_workers=self._threads, mp_context=multiprocessing.get_context("spawn"),
                                    initializer=_init_worker, initargs=(self._variants,)) as matchers:

            decoding = {decoders.submit(self._decode, file): file for file in self._files}
            matching = {}

            for future in as_completed(decoding):
                file = decoding[future]
                try:
                    audio, start = future.result()
                except Exception as e:
                    self.logger.file_error(f"\tCould not read '{file}': {e}")
                    self._finished(results, file, self._result(error=str(e)))
                    continue
                matching[matchers.submit(_match, audio)] = (file, start)

            for future in as_completed(matching):
                file, start = matching[future]
                try:
                    frame, score, speed = future.result()
                except Exception as e:
                    self.logger.file_error(f"\tError detecting in '{file}': {e}")
                    self._finished(results, file, self._result(error=str(e)))
                    continue
                self._finished(results, file, self._result(frame, score, speed, start))
                self.logger.debug(f"\t'{file}': best match at {results[file]['offset']}s, "
                                  f"score {results[file]['score']}, speed {results[file]['speed']}.")

        self.logger.debug("Detection complete.")
        self.logger.empty_line()
        return {file: results[file] for file in self._files}

    def run(self):
        self._load_snippet()
        return self._detect()
