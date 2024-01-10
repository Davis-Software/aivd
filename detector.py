from __future__ import annotations

import uuid
import threading
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

        self._output_data = {}

        self._loader()

    def _ffmpeg_thread(self, file, target):
        pass

    def _loader(self):
        try:
            self.logger.info("Loading libraries...")
            from numpy import argmax
            from librosa import load
            from scipy.signal import correlate
            self.logger.debug("Libraries loaded.")

        except ImportError as e:
            self.logger.error(f"Error loading libraries: {e}")
            exit(1)

        self.logger.info("Loading base file...")
        try:
            self.__y_find, self.__sr = load(self._base_file, sr=None, duration=self.time if self.time > 0 else None)
        except Exception as e:
            self.logger.error(f"Error loading base file: {e}")
            exit(2)
        self.logger.debug("Base file loaded.")

    def convert(self):
        ready, to_convert = os_helpers.is_audio_files(self._files)
        converter_map = {}

        for file in to_convert:
            converter_map[file] = f"{uuid.uuid4().hex}.wav"
            


