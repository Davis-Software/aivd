import os
import sys
import json
import click
import multiprocessing

from colorama import Fore, Style

from detector import Detector, DetectorError

from utils import os_helpers
from utils.logger import Logger
from utils.progress import Progress

__version__ = "3.1.0"

_PERMITTED_EXTENSIONS = ["mp4", "mkv", "avi", "mov", "wmv", "mp3", "wav", "flac", "ogg", "m4a", "wma"]


def print_version(ctx, _param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(__version__)
    ctx.exit()


def print_text(data):
    for file, result in data.items():
        click.echo(f"{Fore.RESET}{os.path.basename(file)} {Fore.CYAN}({Fore.WHITE}{file}{Fore.CYAN})")
        if result["error"] is not None:
            click.echo(f"\t{Fore.RED}-> error: {Fore.RESET}{result['error']}{Style.RESET_ALL}")
        elif result["found"]:
            speed = f", speed {result['speed']}" if result["speed"] != 1 else ""
            click.echo(f"\t{Fore.GREEN}-> {Fore.RESET}{result['offset']}{Fore.WHITE}s {Fore.RESET}offset "
                       f"{Fore.WHITE}(score {result['score']}{speed}){Style.RESET_ALL}")
        else:
            click.echo(f"\t{Fore.YELLOW}-> not found {Fore.WHITE}(best score {result['score']} "
                       f"at {result['offset']}s){Style.RESET_ALL}")


@click.command()
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, allow_dash=True), metavar="INPUT_FILE")
@click.argument("directory", type=click.Path(exists=True, file_okay=False), metavar="DIRECTORY")
@click.option("-r", "--recursive", is_flag=True, help="Search recursively in the specified directory.")
@click.option("-e", "--extension", type=str, default=','.join(_PERMITTED_EXTENSIONS), show_default=True,
              help="The extensions of the video/audio files to search in (case-insensitive). "
                   "Comma separated list, or '*' for all files.")
@click.option("-x", "--exclude", type=str, default="", help="Extensions to exclude from the search. "
                                                            "Comma separated list. Default is no exclusions.")
@click.option("-t", "--time", "time_", type=int, default=-1, help="How many seconds of the input audio file "
                                                                  "to search for. Default is the whole audio file.")
@click.option("-w", "--window", type=click.IntRange(min=1), default=60, show_default=True,
              help="How many seconds at the start (or end, see --from-end) of each file to search in. If this is "
                   "shorter than the input audio, it is extended automatically (see --strict-window).")
@click.option("--from-end", is_flag=True,
              help="Search the last --window seconds of each file instead of the first, e.g. for end credits. "
                   "Offsets are still reported from the start of the file.")
@click.option("--strict-window", is_flag=True,
              help="Exit with an error instead of extending --window when it is shorter than the input audio.")
@click.option("-s", "--min-score", type=click.FloatRange(0, 1), default=0.5, show_default=True,
              help="Minimum match score (0-1) for the input audio to count as found in a file.")
@click.option("--no-speed-search", is_flag=True,
              help="Only match at normal speed. By default the PAL speed-up (4%) and its reverse are tried too, "
                   "with and without pitch shift.")
@click.option("-f", "--format", "format_", type=click.Choice(["json", "txt", "raw"]), default="txt",
              show_default=True, help="The output format.")
@click.option("-c", "--threads", type=click.IntRange(1, os_helpers.thread_count()),
              default=os_helpers.default_threads, show_default="half the CPU threads",
              help="The number of processes used for the audio search.")
@click.option("--ffmpeg", type=click.Path(exists=True, dir_okay=False), default=None,
              help="The path to the ffmpeg executable. Default is ffmpeg from PATH.")
@click.option("--ffmpeg-processes", type=click.IntRange(min=1), default=os_helpers.default_threads,
              show_default="half the CPU threads",
              help="The number of ffmpeg processes to run at the same time.")
@click.option("--ffmpeg-args", type=str, default=None,
              help="Additional output arguments for ffmpeg, e.g. \"-map 0:a:1\" to use the second audio track. "
                   "Pass them in quotes.")
@click.option("--progress", is_flag=True,
              help="Print progress updates to stderr, also with --silent. With -f json/raw they are JSON objects, "
                   "one per line, and the normal log output is turned off so stderr stays machine-readable.")
@click.option("--silent", is_flag=True, help="Do not print anything but the final output.")
@click.option("--debug", is_flag=True, help="Print debug information.")
@click.option("--dry-run", is_flag=True, help="Do not run the search, just print the parameters and found files.")
@click.option("--version", is_flag=True, help="Print the version number and exit.", callback=print_version,
              expose_value=False, is_eager=True)
def main(input_file, directory, recursive, extension, exclude, time_, window, from_end, strict_window, min_score,
         no_speed_search, format_, threads, ffmpeg, ffmpeg_processes, ffmpeg_args, progress, silent, debug, dry_run):
    """
    Find the INPUT_FILE audio file in the specified video or audio files in a folder and return the time index.

    \b
    INPUT_FILE: The audio file to search for, or - to read it from stdin.
    DIRECTORY: The directory with the video or audio files to search in.

    \b
    Exit codes: 0 = success, 1 = at least one file could not be searched or a fatal error, 2 = invalid usage.
    """

    reporter = Progress(progress, as_json=format_ in ("json", "raw"))
    logger = Logger(silent, debug, events=reporter if reporter.as_json else None)

    if time_ != -1 and time_ < 1:
        raise click.BadParameter("must be greater than 0.", param_hint="'-t' / '--time'")

    input_data = None
    if input_file == "-":
        if sys.stdin.isatty():
            raise click.BadParameter("is '-', but nothing is piped into stdin.", param_hint="INPUT_FILE")
        input_data = sys.stdin.buffer.read()
        if not input_data:
            raise click.BadParameter("is '-', but stdin is empty.", param_hint="INPUT_FILE")

    if ffmpeg is None:
        ffmpeg = os_helpers.find_ffmpeg()
        if ffmpeg is None:
            logger.error("ffmpeg was not found on PATH. Install it or pass its location with --ffmpeg.")
            sys.exit(1)
    if not os.access(ffmpeg, os.X_OK):
        logger.error(f"ffmpeg at '{ffmpeg}' is not executable.")
        sys.exit(1)

    logger.info("Starting AIVD...")
    logger.debug(f"AIVD Version: {__version__}")
    logger.debug("Starting with the following parameters:")
    logger.debug(f"\tInput file: {'stdin (' + str(len(input_data)) + ' bytes)' if input_data else repr(input_file)}")
    logger.debug(f"\tDirectory: '{directory}'")
    logger.debug(f"\tRecursive: {recursive}")
    logger.debug(f"\tExtension: {extension}")
    logger.debug(f"\tExclude: {exclude}")
    logger.debug(f"\tTime: {time_}")
    logger.debug(f"\tWindow: {window}{' (strict)' if strict_window else ''}{' from end' if from_end else ''}")
    logger.debug(f"\tMin score: {min_score}")
    logger.debug(f"\tSpeed search: {not no_speed_search}")
    logger.debug(f"\tFormat: {format_}")
    logger.debug(f"\tThreads: {threads}")
    logger.debug(f"\tFFmpeg: '{ffmpeg}'")
    logger.debug(f"\tFFmpeg processes: {ffmpeg_processes}")
    logger.debug(f"\tFFmpeg args: {ffmpeg_args}")
    logger.empty_line()

    files = os_helpers.file_walker(directory, logger, recursive, extension, exclude)
    logger.info(f"Found {len(files)} files to search in.")
    logger.empty_line()

    if dry_run:
        logger.info("Dry run, exiting!")
        return

    detector = Detector(input_file, files, time_, window, ffmpeg, logger, threads, ffmpeg_processes,
                        ffmpeg_args, min_score, strict_window, from_end, not no_speed_search,
                        base_data=input_data, on_result=reporter.file_done)
    reporter.start(len(files))
    try:
        data = detector.run()
    except DetectorError as e:
        logger.error(str(e))
        sys.exit(1)
    reporter.finish(data)

    if format_ == "json":
        click.echo(json.dumps(data, indent=2))
    elif format_ == "raw":
        click.echo(json.dumps(data))
    else:
        print_text(data)

    failed = sum(1 for result in data.values() if result["error"] is not None)
    if failed:
        if not reporter.as_json:  # the "done" event already says so
            logger.error(f"{failed} of {len(data)} files could not be searched.")
        sys.exit(1)


if __name__ == '__main__':
    multiprocessing.freeze_support()  # required for multiprocessing in PyInstaller builds
    main()
