import time
import subprocess
from uuid import uuid4


def make_input_file(file_path: str, to_max: int, ffmpeg):
    name = f"/tmp/{str(uuid4())}.wav"
    ffmpeg = subprocess.Popen(
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
    ffmpeg.wait()

    if ffmpeg.returncode != 0:
        raise Exception("Failed to convert file", file_path)

    return name
