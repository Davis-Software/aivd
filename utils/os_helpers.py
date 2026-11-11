import os
import sys
import subprocess
import multiprocessing

from utils.logger import Logger


def subprocess_env():
    """
    Environment for external programs (ffmpeg).

    In a PyInstaller build the bootloader points LD_LIBRARY_PATH at the bundled libraries. Child processes
    inherit it and the system ffmpeg then loads the bundled (possibly older) libstdc++ etc. and crashes, so
    restore the original value before spawning anything.
    """
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is not None:
            env["LD_LIBRARY_PATH"] = original
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


def find_ffmpeg():
    output = subprocess.check_output(['which', 'ffmpeg'])
    return output.decode('utf-8').strip()


def thread_count():
    return multiprocessing.cpu_count()


def file_walker(files_path, logging: Logger, recursive=False, extension="*", extension_skip=""):
    files = os.listdir(files_path)
    output = []

    for i, file in enumerate(files):
        file = os.path.join(files_path, file)

        if not os.path.isfile(file) and recursive:
            output.extend(
                file_walker(file, logging, recursive, extension, extension_skip)
            )
            continue

        if extension != "*" and True not in [file.endswith(val) for val in extension.split(",")]:
            logging.debug(f"Skipping file {i + 1} ('{file}') of {len(files)} as "
                          f"it does not match the specified file extension '{extension}'")
            continue

        if extension_skip != "" and True in [file.endswith(val) for val in extension_skip.split(",")]:
            logging.debug(f"Skipping file {i + 1} ('{file}') of {len(files)} as "
                          f"it matches the specified file extension '{extension_skip}'")
            continue

        logging.debug(f"Found file '{file}' ({i + 1} of {len(files)})")
        output.append(file)

    return output


def is_audio_files(files):
    ready_files = []
    to_convert_files = []

    for file in files:
        if file.endswith(".wav"):
            ready_files.append(file)
        else:
            to_convert_files.append(file)

    return ready_files, to_convert_files
