import os
import sys
import shutil

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
    """Path of ffmpeg on PATH, or None."""
    return shutil.which("ffmpeg")


def thread_count():
    """CPUs this process may actually use (respects affinity / taskset where the platform supports it)."""
    if hasattr(os, "process_cpu_count"):  # Python 3.13+
        return os.process_cpu_count() or 1
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0)) or 1
    return os.cpu_count() or 1


def default_threads():
    return max(1, thread_count() // 2)


def parse_extensions(value):
    """'mp4, .MKV,avi' -> {'mp4', 'mkv', 'avi'}; '*' -> None (everything)."""
    if value.strip() == "*":
        return None
    return {ext.strip().lstrip(".").lower() for ext in value.split(",") if ext.strip()}


def _extension(path):
    return os.path.splitext(path)[1].lstrip(".").lower()


def file_walker(files_path, logging: Logger, recursive=False, extension="*", extension_skip=""):
    include = parse_extensions(extension)
    exclude = parse_extensions(extension_skip) or set()

    if recursive:
        candidates = [os.path.join(root, name) for root, _dirs, names in os.walk(files_path) for name in names]
    else:
        candidates = [entry.path for entry in os.scandir(files_path) if entry.is_file()]

    output = []
    for file in sorted(candidates):
        ext = _extension(file)
        if include is not None and ext not in include:
            logging.debug(f"Skipping '{file}': extension '{ext}' is not in '{extension}'")
            continue
        if ext in exclude:
            logging.debug(f"Skipping '{file}': extension '{ext}' is excluded")
            continue
        logging.debug(f"Found file '{file}'")
        output.append(file)

    return output
