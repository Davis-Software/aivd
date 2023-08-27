import os
import time
import json
import logging
import argparse
import threading
import subprocess

from uuid import uuid4
from numpy import argmax
from librosa import load
from scipy.signal import correlate


def make_input_file(file_path: str, to_max: int, ffmpeg):
    name = f"/tmp/{str(uuid4())}.wav"
    subprocess.Popen(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "quiet",
            "-to",
            str(to_max),
            "-i",
            file_path,
            name
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(.5)

    return name


def find_offset_thread(within_file, y_find, sample_rate, semaphore, window, data_target, ffmpeg):
    semaphore.acquire()
    logging.debug(f"Processing file '{within_file.split('/').pop()}")

    temp_file = make_input_file(within_file, window, ffmpeg)
    y_within, _ = load(temp_file, sr=sample_rate)
    os.remove(temp_file)

    c = correlate(y_within, y_find[:sample_rate*window], mode='valid', method='fft')
    peak = argmax(c)
    offset = round(peak / sample_rate, 2)

    semaphore.release()
    data_target[within_file] = offset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--find-offset-of', metavar='<audio file>', type=str, help='Find the offset of file')
    parser.add_argument('--within', metavar='<folder>', type=str, help='Within files folder', default=".")
    parser.add_argument('--extension', metavar='<file extension>', type=str, default="*",
                        help='File with the extension to use')
    parser.add_argument('--window', metavar='<seconds>', type=int, default=60,
                        help='Only use first n seconds of a target audio')
    parser.add_argument("--log-level", metavar="<level>", type=str, default="info",
                        help="Log Level: debug, info, warning, error")
    parser.add_argument("--raw", metavar="<boolean>", type=bool, default=False,
                        help="Displays the result as raw json data instead of formatting it")
    parser.add_argument("--ffmpeg", metavar="<path>", type=str, default="/usr/bin/ffmpeg",
                        help="FFMPEG path")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper(), format='%(levelname)s - %(message)s')
    offsets = dict()
    semaphore = threading.Semaphore(3)
    y_find, sample_rate = load(args.find_offset_of, sr=None)

    logging.debug("Init complete - processing files...")

    files = os.listdir(args.within)
    logging.info(f"Processing {len(files)} files")

    for i, file in enumerate(files):
        file = os.path.join(args.within, file)

        if args.extension != "*" and not file.endswith(args.extension):
            logging.debug(f"Skipping file {i + 1} ('{file}') of {len(files)} as"
                          f"it does not match the specified file extension '{args.extension}'")
            continue

        thread = threading.Thread(
            target=find_offset_thread,
            args=(file, y_find, sample_rate, semaphore, args.window, offsets, args.ffmpeg, ),
            daemon=True
        )
        thread.start()

    while semaphore._value != 3:
        time.sleep(.1)

    logging.info("Processing compete.")

    if args.raw:
        print(json.dumps(offsets))

    else:
        for file, offset in offsets.items():
            print(f"{file.split('/').pop()}\n\t-> {offset}s offset")


if __name__ == '__main__':
    main()
