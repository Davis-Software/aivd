from __future__ import annotations

import os
import time
import uuid
import threading
import traceback
import subprocess
import multiprocessing

from utils import os_helpers
from utils.logger import Logger


def _detector_thread(file_obj):
    try:
        load, correlate, argmax, y_find, sr, logger = file_obj["args"]
    except KeyError:
        return {"file": None, "offset": -1}

    logger.debug(f"\tDetecting in '{file_obj['name']}'...")

    try:
        y_within, _ = load(file_obj["location"], sr=sr)
        c = correlate(y_within, y_find, mode='valid', method='fft')
        peak = argmax(c)
        offset = round(peak / sr, 2)

        logger.debug(f"\tDetected in '{file_obj['name']}' at {offset} seconds.")
    except Exception as e:
        logger.error(f"\tError detecting in '{file_obj['name']}': '{e}'", traceback.format_exc())
        offset = -1

    return {
        "file": file_obj["name"],
        "offset": offset
    }


class Detector:
    def __init__(self, base_file: str, files: list[str], time_: int, window: int, ffmpeg: str, logger: Logger,
                 clean=True, aivd_threads=1, ffmpeg_processes=1):
        self._base_file = base_file
        self._files = files
        self.__ready_files, self.__to_convert = os_helpers.is_audio_files(files)

        self.__load = None
        self.__correlate = None
        self.__argmax = None

        self._ffmpeg_semaphore = threading.Semaphore(ffmpeg_processes)
        self._threads = aivd_threads

        self.time = time_
        self.window = window
        self.ffmpeg = ffmpeg
        self.logger = logger
        self.clean = clean

        self.__y_find = None
        self.__sr = None

        self.__converter_map = {}

        self._output_data = {}

        self._init()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.logger.error(f"The Application was terminated: {exc_type.__name__}")
        self.clean_up()

    def __ffmpeg_thread(self, file, file_obj, additional_args=None):
        self._ffmpeg_semaphore.acquire()
        target = file_obj["location"]
        self.logger.debug(f"\tConverting '{file}' to '{target}'...")

        ffmpeg_opts = [self.ffmpeg, "-y"]

        if not self.logger.is_debug or self.logger.is_silent:
            ffmpeg_opts.extend(["-loglevel", "quiet"])

        ffmpeg_opts.extend([
            "-to", str(self.window),
            "-i", file,
            target
        ])

        if additional_args is not None:
            ffmpeg_opts.extend(additional_args)

        ffmpeg = subprocess.Popen(
            ffmpeg_opts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        ffmpeg.wait()

        if ffmpeg.returncode == 0:
            file_obj["success"] = True
            self.logger.debug(f"\tConverted '{file}' to '{target}'.")
        else:
            self.logger.error(
                f"\tError converting '{file}' to '{target}'!",
                ffmpeg.stderr.read().decode('utf-8') + "\n" + ffmpeg.stdout.read().decode('utf-8')
            )

        file_obj["complete"] = True
        self._ffmpeg_semaphore.release()

    def _init(self):
        self.logger.info("Loading libraries...")
        try:
            from numpy import argmax
            from librosa import load
            from scipy.signal import correlate

            self.__load = load
            self.__correlate = correlate
            self.__argmax = argmax
        except Exception as e:
            self.logger.error(f"Error loading libraries: '{e}'")
            exit(1)
        self.logger.debug("Libraries loaded.")
        self.logger.empty_line()

    def _load(self):
        self.logger.info("Loading base file...")
        try:
            self.__y_find, self.__sr = self.__load(self._base_file, sr=None,
                                                   duration=self.time if self.time > 0 else None)
        except Exception as e:
            self.logger.error(f"Error loading base file: '{e}'")
            exit(2)
        self.logger.debug("Base file loaded.")
        self.logger.empty_line()

    def _convert(self, ffmpeg_args=None):
        if len(self.__to_convert) == 0:
            self.logger.info("No files to convert. Skipping conversion...")
            return

        self.logger.info(f"Converting {len(self.__to_convert)} files...")

        for file in self.__to_convert:
            file_obj = {
                "location": f"/tmp/{uuid.uuid4().hex}.wav",
                "success": False,
                "complete": False
            }

            threading.Thread(
                target=self.__ffmpeg_thread,
                args=(file, file_obj, ffmpeg_args, )
            ).start()

            self.__converter_map[file] = file_obj

        # Wait for all conversions to complete
        while not all([self.__converter_map[file]["complete"] for file in self.__converter_map]):
            time.sleep(.1)

        self.logger.debug("Conversions complete.")
        self.logger.empty_line()

    def _detect(self):
        self.logger.info(f"Detecting in {len(self.__ready_files)} original files and {len(self.__converter_map)} "
                         f"converted files...")
        files = []

        for file in self.__ready_files:
            files.append({
                "name": file,
                "location": file,
            })
        for file in self.__converter_map:
            if not self.__converter_map[file]["success"]:
                continue
            files.append({
                "name": file,
                "location": self.__converter_map[file]["location"],
                "args": (self.__load, self.__correlate, self.__argmax, self.__y_find, self.__sr, self.logger)
            })

        with multiprocessing.Pool(processes=self._threads) as pool:
            self.logger.debug(f"\tUsing {self._threads} threads.")
            results = pool.map(_detector_thread, files)

        for result in results:
            if result["file"] is None:
                continue
            self._output_data[result["file"]] = result["offset"]

        self.logger.debug("Detection complete.")
        self.logger.empty_line()

    def clean_up(self):
        if not self.clean:
            self.logger.debug("Skipping clean up.")
            return

        self.logger.info("Cleaning up...")
        for file in self.__converter_map:
            file = self.__converter_map[file]["location"]
            if os.path.exists(file):
                os.remove(file)
                self.logger.debug(f"\tRemoved '{file}'")
        self.logger.debug("Clean up complete.")
        self.logger.empty_line()

    def run(self, ffmpeg_args=None):
        self._load()
        self._convert(ffmpeg_args)
        self._detect()

        return self._output_data
