import os
import subprocess


def find_ffmpeg():
    output = subprocess.check_output(['which', 'ffmpeg'])
    return output.decode('utf-8').strip()


def file_walker(files_path, logging, recursive=False, extension="*", extension_skip=""):
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
