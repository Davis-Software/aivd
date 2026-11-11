from __future__ import annotations

import math
import shlex
import subprocess
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

import numpy as np

from utils import os_helpers
from utils.logger import Logger


class DetectorError(Exception):
    """An error that makes the whole run impossible (bad snippet, bad options)."""


# Set once per worker process by _init_worker, so the snippet isn't sent along with every job.
_snippet = None
_snippet_norm = None


def _init_worker(snippet):
    global _snippet, _snippet_norm
    _snippet = snippet
    _snippet_norm = float(np.sqrt(np.dot(snippet, snippet)))


def _match(audio):
    """
    Slide the snippet over `audio` and return (best sample index, score).

    The score is the normalised cross-correlation at that position: 1.0 means the audio there is the snippet
    (up to volume), values near 0 mean no similarity. Normalising by the local energy also stops loud passages
    from winning just because they are loud.
    """
    from scipy.signal import correlate

    n = len(_snippet)
    audio = audio.astype(np.float64)
    corr = correlate(audio, _snippet, mode="valid", method="fft")

    energy = np.concatenate(([0.0], np.cumsum(audio * audio)))
    local_norm = np.sqrt(np.maximum(energy[n:] - energy[:-n], 0.0))
    denominator = local_norm * _snippet_norm

    ncc = np.zeros_like(corr)
    np.divide(corr, denominator, out=ncc, where=denominator > 1e-9)

    peak = int(np.argmax(ncc))
    return peak, float(min(ncc[peak], 1.0))


class Detector:
    def __init__(self, base_file: str, files: list[str], time_: int, window: int, ffmpeg: str, logger: Logger,
                 aivd_threads=1, ffmpeg_processes=1, ffmpeg_args: str | None = None, min_score=0.3,
                 strict_window=False):
        self._base_file = base_file
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

        self._snippet = None
        self._sr = None

    def _load_snippet(self):
        self.logger.info("Loading base file...")
        try:
            from librosa import load
            snippet, self._sr = load(self._base_file, sr=None, mono=True,
                                     duration=self.time if self.time > 0 else None)
        except Exception as e:
            raise DetectorError(f"Could not load base file '{self._base_file}': {e}") from e

        if len(snippet) == 0 or not np.any(snippet):
            raise DetectorError(f"Base file '{self._base_file}' is empty or silent.")
        self._snippet = snippet.astype(np.float64)

        length = len(snippet) / self._sr
        self.logger.debug(f"\tBase file: {length:.2f}s at {self._sr} Hz.")

        if self.window <= length:
            if self.strict_window:
                raise DetectorError(f"The window ({self.window}s) must be longer than the base file "
                                    f"({length:.2f}s). Increase --window or shorten the base file with --time.")
            new_window = math.ceil(length) + self.window
            self.logger.warning(f"The window ({self.window}s) is shorter than the base file ({length:.2f}s). "
                                f"Extending it to {new_window}s so the base file can start anywhere in the first "
                                f"{self.window}s. Use --strict-window to make this an error instead.")
            self.window = new_window
        self.logger.empty_line()

    def _decode(self, file):
        """Decode the first `window` seconds of `file` to mono float32 at the snippet's sample rate."""
        command = [
            self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-t", str(self.window), "-i", file,
            "-vn", "-sn", "-dn",
            *self._ffmpeg_args,
            "-ac", "1", "-ar", str(self._sr), "-f", "f32le", "pipe:1",
        ]
        self.logger.debug(f"\tDecoding '{file}': {shlex.join(command)}")

        result = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL,
                                env=os_helpers.subprocess_env())
        if result.returncode != 0:
            lines = result.stderr.decode("utf-8", errors="replace").strip().splitlines()
            message = " / ".join(line.strip() for line in lines if line.strip()) or f"exit code {result.returncode}"
            raise RuntimeError(f"ffmpeg failed: {message}")

        audio = np.frombuffer(result.stdout, dtype="<f4")
        if len(audio) < len(self._snippet):
            raise RuntimeError(f"only {len(audio) / self._sr:.2f}s of audio, "
                               f"shorter than the base file ({len(self._snippet) / self._sr:.2f}s)")
        return audio

    def _result(self, peak=None, score=None, error=None):
        if error is not None:
            return {"offset": None, "score": None, "found": False, "error": error}
        return {
            "offset": round(peak / self._sr, 2),
            "score": round(score, 3),
            "found": score >= self.min_score,
            "error": None,
        }

    def _detect(self):
        self.logger.info(f"Searching {len(self._files)} files...")
        self.logger.debug(f"\tUsing {self._ffmpeg_processes} ffmpeg processes and {self._threads} detector processes.")
        results = {}

        # "spawn": the process pool is started while decoder threads are running, and forking a multi-threaded
        # process can deadlock.
        with ThreadPoolExecutor(max_workers=self._ffmpeg_processes) as decoders, \
                ProcessPoolExecutor(max_workers=self._threads, mp_context=multiprocessing.get_context("spawn"),
                                    initializer=_init_worker, initargs=(self._snippet,)) as matchers:

            decoding = {decoders.submit(self._decode, file): file for file in self._files}
            matching = {}

            for future in as_completed(decoding):
                file = decoding[future]
                try:
                    audio = future.result()
                except Exception as e:
                    self.logger.error(f"\tCould not read '{file}': {e}")
                    results[file] = self._result(error=str(e))
                    continue
                matching[matchers.submit(_match, audio)] = file

            for future in as_completed(matching):
                file = matching[future]
                try:
                    peak, score = future.result()
                except Exception as e:
                    self.logger.error(f"\tError detecting in '{file}': {e}")
                    results[file] = self._result(error=str(e))
                    continue
                results[file] = self._result(peak, score)
                self.logger.debug(f"\t'{file}': best match at {results[file]['offset']}s, "
                                  f"score {results[file]['score']}.")

        self.logger.debug("Detection complete.")
        self.logger.empty_line()
        return {file: results[file] for file in self._files}

    def run(self):
        self._load_snippet()
        return self._detect()
