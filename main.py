import json
import click
import os.path

from colorama import Fore, Style

from detector import Detector

from utils import os_helpers
from utils.logger import Logger

__version__ = "2.1.4"

_PERMITTED_EXTENSIONS = ["mp4", "mkv", "avi", "mov", "wmv", "mp3", "wav", "flac", "ogg", "m4a", "wma"]


def print_version(ctx, _param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(__version__)
    ctx.exit()


def load_legacy(ctx, _param, value):
    if not value or ctx.resilient_parsing:
        return
    from legacy.main import main as legacy_main
    legacy_main()
    ctx.exit()


@click.command()
@click.argument("input_file", type=click.Path(exists=True), metavar="INPUT_FILE")
@click.argument("directory", type=click.Path(exists=True), metavar="DIRECTORY")
@click.option("-r", "--recursive", is_flag=True, help="Search recursively in the specified directory.")
@click.option("-e", "--extension", type=str, default=','.join(_PERMITTED_EXTENSIONS),
              help="The extension of the video/audio files to search in. "
                   f"Default is '{','.join(_PERMITTED_EXTENSIONS)}'. Can be a comma separated list.")
@click.option("-x", "--exclude", type=str, default="", help="Exclude the specified extension from the search. "
                                                            "Default is no exclusions. Can be a comma separated list.")
@click.option("-t", "--time", "time_", type=int, default=-1, help="How many seconds of the input audio file "
                                                                  "to search for. Default is the whole audio file.")
@click.option("-w", "--window", type=int, default=60, help="The window size in seconds to search for the audio file. "
                                                           "Default is 60 seconds.")
@click.option("-f", "--format", "format_", type=click.Choice(["json", "txt", "raw"]), default="txt",
              help="The output format. Default is TEXT.")
@click.option("-c", "--threads", type=int, default=lambda: os_helpers.thread_count() / 2,
              help="The number of CPU threads to use. Default is half the number of CPU cores. The number is used for "
                   "both the audio file conversion via ffmpeg and the audio file search.")
@click.option("--ffmpeg", type=click.Path(exists=True), default=lambda: os_helpers.find_ffmpeg(),
              help="The path to the ffmpeg executable. Default is the system path.")
@click.option("--ffmpeg-processes", type=int, default=1, help="The number of ffmpeg processes to run at the same time."
                                                              "Default is 1.")
@click.option("--ffmpeg-args", type=str, default=None, help="Additional arguments to pass to ffmpeg."
                                                            "Best pass them in quotes.")
@click.option("--no-clean", is_flag=True, help="Do not clean up temporary files.")
@click.option("--silent", is_flag=True, help="Do not print anything but the final output to the console.")
@click.option("--debug", is_flag=True, help="Print debug information to the console.")
@click.option("--dry-run", is_flag=True, help="Do not run the program, just print the parameters.")
@click.option("--version", is_flag=True, help="Print the version number and exit.", callback=print_version,
              expose_value=False, is_eager=True)
@click.option("--legacy", is_flag=True, help="Use the legacy cli.", callback=load_legacy,
              expose_value=False, is_eager=True)
def main(input_file, directory, recursive, extension, exclude, time_, window, format_, threads, ffmpeg,
         ffmpeg_processes, ffmpeg_args, no_clean, silent, debug, dry_run):
    """
    Find the INPUT_FILE audio file in the specified video or audio files in a folder and return the time index.

    \b
    INPUT_FILE: The audio file to search for.
    DIRECTORY: The directory with the video or audio files to search in.
    """

    logger = Logger(silent, debug)

    if time_ != -1 and time_ < 1:
        logger.error("Time must be greater than 0.")
        exit(-1)
    if window < 1:
        logger.error("Window must be greater than 0.")
        exit(-1)
    if threads < 1 or threads > os_helpers.thread_count():
        logger.error(f"Threads must be between 1 and {os_helpers.thread_count()} (CPU thread count).")
        exit(-1)

    logger.info("Starting AIVD...")
    logger.debug(f"AIVD Version: {__version__}")
    logger.debug("Starting with the following parameters:")
    logger.debug(f"\tInput file: '{input_file}'")
    logger.debug(f"\tDirectory: '{directory}'")
    logger.debug(f"\tRecursive: {recursive}")
    logger.debug(f"\tExtension: {extension}")
    logger.debug(f"\tExclude: {exclude}")
    logger.debug(f"\tTime: {time_}")
    logger.debug(f"\tWindow: {window}")
    logger.debug(f"\tFormat: {format_}")
    logger.debug(f"\tThreads: {threads}")
    logger.debug(f"\tFFmpeg: '{ffmpeg}'")
    logger.debug(f"\tFFmpeg processes: {ffmpeg_processes}")
    logger.debug(f"\tFFmpeg args: {ffmpeg_args}")
    logger.debug(f"\tSkipping clean up: {no_clean}")
    logger.empty_line()

    logger.info("Checking if ffmpeg exists...")
    if not os.path.exists(ffmpeg):
        logger.error(f"ffmpeg not found at '{ffmpeg}'.")
        exit(-1)
    logger.debug("ffmpeg found.")
    logger.empty_line()

    files = os_helpers.file_walker(directory, logger, recursive, extension, exclude)
    logger.empty_line()

    ready, to_convert = os_helpers.is_audio_files(files)
    logger.info(f"Found {len(files)} files to search in{':' if debug else '.'}")
    logger.debug(f"\t{len(ready)} audio files.")
    logger.debug(f"\t{len(to_convert)} files to be converted.")
    logger.empty_line()

    if dry_run:
        logger.info("Dry run, exiting!")
        return

    with Detector(input_file, files, time_, window, ffmpeg, logger, not no_clean, threads, ffmpeg_processes)\
            as detector:
        data = detector.run(
            ffmpeg_args if (ffmpeg_args is not None and ffmpeg_args != "" and ffmpeg_args != "None") else None
        )

    if format_ == "json":
        logger.debug("Outputting JSON...")
        logger.empty_line()

        click.echo(json.dumps(data))

    elif format_ == "txt":
        logger.debug("Outputting in formatted text...")
        logger.empty_line()

        for file, offset in data.items():
            click.echo(f"{Fore.RESET}{file.split('/').pop()} {Fore.CYAN}({Fore.WHITE}{file}{Fore.CYAN})"
                       f"\n\t{Fore.GREEN}-> {Fore.RESET}{offset}{Fore.WHITE}s {Fore.RESET}offset{Style.RESET_ALL}")
        logger.empty_line()

    elif format_ == "raw":
        click.echo(json.dumps(data).encode("utf-8"))


if __name__ == '__main__':
    main()
