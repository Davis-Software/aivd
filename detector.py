from __future__ import annotations

import os
import time
import uuid
import threading
import subprocess
import multiprocessing

from utils import os_helpers
from utils.logger import Logger


class Detector:
    def __init__(self, base_file: str, files: list[str], time: int, window: int, ffmpeg: str, logger: Logger,
                 clean=True, threads=1):
        self._base_file = base_file
        self._files = files

        self._ffmpeg_semaphore = threading.Semaphore(threads)
        self._detector_semaphore = multiprocessing.Semaphore(threads)

        self.time = time
        self.window = window
        self.ffmpeg = ffmpeg
        self.logger = logger
        self.clean = clean

        self.__y_find = None
        self.__sr = None

        self.__converter_map = {}

        self._output_data = {}

        self._loader()

    def _ffmpeg_thread(self, file, file_obj):
        self._ffmpeg_semaphore.acquire()
        target = file_obj["location"]

        self.logger.debug(f"\tConverting {file} to {target}...")
        ffmpeg = subprocess.Popen(
            [
                self.ffmpeg,
                "-y",
                "-loglevel",
                "quiet",
                "-to",
                str(self.window),
                "-i",
                file,
                target
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        ffmpeg.wait()

        if ffmpeg.returncode == 0:
            file_obj["success"] = True
            self.logger.debug(f"\tConverted {file} to {target}.")
        else:
            self.logger.error(f"\tError converting {file} to {target}: {ffmpeg.stderr.read().decode('utf-8')}")

        file_obj["complete"] = True
        self._ffmpeg_semaphore.release()

    def _loader(self):
        self.logger.info("Loading libraries...")
        try:
            from numpy import argmax
            from librosa import load
            from scipy.signal import correlate
        except ImportError as e:
            self.logger.error(f"Error loading libraries: {e}")
            exit(1)
        self.logger.debug("Libraries loaded.")
        self.logger.empty_line()

        self.logger.info("Loading base file...")
        try:
            self.__y_find, self.__sr = load(self._base_file, sr=None, duration=self.time if self.time > 0 else None)
        except Exception as e:
            self.logger.error(f"Error loading base file: {e}")
            exit(2)
        self.logger.debug("Base file loaded.")
        self.logger.empty_line()

    def convert(self):
        ready, to_convert = os_helpers.is_audio_files(self._files)
        self.logger.info(f"Converting {len(to_convert)} files...")

        for file in to_convert:
            file_obj = {
                "location": f"/tmp/{uuid.uuid4().hex}.wav",
                "success": False,
                "complete": False
            }

            threading.Thread(
                target=self._ffmpeg_thread,
                args=(file, file_obj, )
            ).start()

            self.__converter_map[file] = file_obj

        # Wait for all conversions to complete
        while not all([self.__converter_map[file]["success"] for file in self.__converter_map]):
            time.sleep(.1)

        self.logger.debug("Conversions complete.")
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
                self.logger.debug(f"\tRemoved {file}")
        self.logger.debug("Clean up complete.")

    def run(self):
        self.convert()
        self.clean_up()

        return self._output_data
