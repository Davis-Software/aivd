import os
import time
import json
import logging
import threading

from numpy import argmax
from librosa import load
from scipy.signal import correlate

from arg_parser import parse_sys_args
from ffmpeg_utils import make_input_file


def find_offset_thread(within_file, y_find, sample_rate, semaphore, window, data_target, ffmpeg):
    semaphore.acquire()
    logging.debug(f"Processing file '{within_file.split('/').pop()}")

    try:
        temp_file = make_input_file(within_file, window, ffmpeg)
        if temp_file is None:
            logging.error(f"Conversion of {within_file} failed. Skipping...")
            return

        y_within, _ = load(temp_file, sr=sample_rate)
        os.remove(temp_file)

        c = correlate(y_within, y_find[:sample_rate*window], mode='valid', method='fft')
        peak = argmax(c)
        offset = round(peak / sample_rate, 2)

        data_target[within_file] = offset

    except Exception as e:
        logging.error(e)

    finally:
        semaphore.release()


def file_walker(files_path, args, y_find, sample_rate, semaphore, offsets):
    files = os.listdir(files_path)
    for i, file in enumerate(files):
        file = os.path.join(files_path, file)

        if not os.path.isfile(file) and args.recursive:
            file_walker(file, args, y_find, sample_rate, semaphore, offsets)
            continue

        if args.extension != "*" and True not in [file.endswith(val) for val in args.extension.split(",")]:
            logging.debug(f"Skipping file {i + 1} ('{file}') of {len(files)} as "
                          f"it does not match the specified file extension '{args.extension}'")
            continue

        if args.extension_skip != "" and True in [file.endswith(val) for val in args.extension_skip.split(",")]:
            logging.debug(f"Skipping file {i + 1} ('{file}') of {len(files)} as "
                          f"it matches the specified file extension '{args.extension_skip}'")
            continue

        thread = threading.Thread(
            target=find_offset_thread,
            args=(file, y_find, sample_rate, semaphore, args.window, offsets, args.ffmpeg,),
            daemon=True
        )
        thread.start()


def main():
    args = parse_sys_args()

    if not os.path.exists(args.ffmpeg) or not os.path.isfile(args.ffmpeg):
        logging.critical("FFMPEG could not be found under the specified path. Please check your configuration.")
        exit(12)

    logging.basicConfig(level=args.log_level.upper(), format='%(levelname)s - %(message)s')
    offsets = dict()
    semaphore = threading.Semaphore(3)
    y_find, sample_rate = load(args.find_offset_of, sr=None)

    logging.debug("Init complete - processing files...")

    file_count = 0
    for _, _, files in os.walk(args.within):
        file_count += len(files)
    logging.info(f"Processing {file_count} files")

    file_walker(args.within, args, y_find, sample_rate, semaphore, offsets)

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
