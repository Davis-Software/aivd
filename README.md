# Audio-In-Video-Detector AIVD

> Developed by [Davis_Software](https://github.com/Davis-Software) &copy; 2024

![GitHub release (latest by date)](https://img.shields.io/github/v/release/Davis-Software/aivd?style=for-the-badge)
![GitHub issues](https://img.shields.io/github/issues-raw/Davis-Software/aivd?style=for-the-badge)
![GitHub closed issues](https://img.shields.io/github/issues-closed/Davis-Software/aivd?style=for-the-badge)
![GitHub all releases](https://img.shields.io/github/downloads/Davis-Software/aivd/total?style=for-the-badge)
![GitHub](https://img.shields.io/github/license/Davis-Software/aivd?style=for-the-badge)

### What is AIVD?
AIVD or Audio-In-Video-Detector finds a specified audio file in the audio track
of video files and returns the audio offset.

Thus, it can for example be used to find the intro of a tv show in its episodes.

### Requirements
* tested on linux; ffmpeg must be on `PATH` or passed with `--ffmpeg`
* `python3.10+` (builds use `python3.12`)
* `ffmpeg` is required
* runtime requirements can be installed with `pip3 install -r requirements.txt`

### Usage
```shell
    aivd [OPTIONS] INPUT_FILE DIRECTORY

        Find the INPUT_FILE audio file in the specified video or audio files in a
        folder and return the time index.
        
        INPUT_FILE: The audio file to search for.
        DIRECTORY: The directory with the video or audio files to search in.
```

| Option                 | Data Type            | Description                                                                                       | Default                                          |
|------------------------|----------------------|---------------------------------------------------------------------------------------------------|--------------------------------------------------|
| `-r`, `--recursive`    | flag                 | Search recursively in the specified directory.                                                    |                                                  |
| `-e`, `--extension`    | `string`             | Extensions of the files to search in (case-insensitive). Comma separated list, or `*` for all.    | `"mp4,mkv,avi,mov,wmv,mp3,wav,flac,ogg,m4a,wma"` |
| `-x`, `--exclude`      | `string`             | Extensions to exclude from the search. Comma separated list.                                      | `""`                                             |
| `-t`, `--time`         | `integer`            | How many seconds of the input audio file to search for.                                           | `-1` (meaning the entire file)                   |
| `-w`, `--window`       | `integer`            | How many seconds at the start (or end) of each file to search in. Extended automatically if too short. | `60`                                        |
| `--from-end`           | flag                 | Search the last `--window` seconds instead of the first (e.g. end credits). Offsets stay from the start. |                                           |
| `--strict-window`      | flag                 | Exit with an error instead of extending `--window` when it is shorter than the input audio.       |                                                  |
| `-s`, `--min-score`    | `float` (0-1)        | Minimum match score for the input audio to count as found in a file.                              | `0.5`                                            |
| `--no-speed-search`    | flag                 | Only match at normal speed (see [How it works](#how-it-works)).                                   |                                                  |
| `-f`, `--format`       | `json \| txt \| raw` | The output format. `raw` is compact JSON.                                                          | `"txt"`                                          |
| `-c`, `--threads`      | `integer`            | The number of processes used for the audio search.                                                | half of the usable CPU threads                   |
| `--ffmpeg`             | `string`             | The path to the ffmpeg executable.                                                                | from `PATH`                                      |
| `--ffmpeg-processes`   | `integer`            | The number of ffmpeg processes to run at the same time.                                           | half of the usable CPU threads                   |
| `--ffmpeg-args`        | `string`             | Additional output arguments for ffmpeg, e.g. `"-map 0:a:1"` for the second audio track.           | `None`                                           |
| `--silent`             | flag                 | Do not print anything but the final output.                                                       |                                                  |
| `--debug`              | flag                 | Print debug information.                                                                          |                                                  |
| `--dry-run`            | flag                 | Do not run the search, just print the parameters and found files.                                 |                                                  |
| `--version`            | flag                 | Print the version number and exit.                                                                |                                                  |
| `--help`               | flag                 | Show help message and exit.                                                                       |                                                  |

Logs go to stderr, so stdout only contains the result and can be piped (e.g. `aivd -f json intro.wav ./episodes | jq`).

### Output
For every file AIVD reports where the input audio matches best and how well it matches:
```json
{
  "episodes/ep01.mkv": {"offset": 17.0, "score": 0.863, "speed": 1.0, "found": true, "error": null},
  "episodes/ep02_pal.mkv": {"offset": 20.0, "score": 0.867, "speed": 1.0427, "found": true, "error": null},
  "episodes/special.mkv": {"offset": 31.0, "score": 0.227, "speed": 1.0, "found": false, "error": null},
  "episodes/broken.mkv": {"offset": null, "score": null, "speed": null, "found": false, "error": "ffmpeg failed: ..."}
}
```
* `offset`: position of the best match in seconds
* `score`: how similar the audio at that position is, from 0 (no similarity) to 1 (identical up to volume and EQ)
* `speed`: playback speed of the file relative to the input audio, e.g. `1.0427` for a PAL speed-up
* `found`: `score >= --min-score`
* `error`: why the file could not be searched, otherwise `null`

Exit codes: `0` success, `1` at least one file could not be searched (or a fatal error), `2` invalid usage.

### How it works
Every file is decoded by ffmpeg to 16 kHz mono and turned into a log-mel spectrogram (40 bands, 10 ms frames).
The input audio is slid over it and compared with a normalised correlation that ignores the overall volume and
constant EQ differences, so re-encoded or remastered audio still matches. Unless `--no-speed-search` is given, the
input audio is also tried at the PAL speed-up (25/24 and 25/23.976) and its reverse, each with and without the
pitch shift that comes with it.

### Compilation
You can use pyinstaller to generate a binary in `./dist/` (on Linux `objdump` from `binutils` is required)
```shell
    pip3 install -r requirements-build.txt
    pyinstaller aivd.spec
```

### CI
The GitLab pipeline (`.gitlab-ci.yml`) builds the Linux binary on every push and runs a smoke test with it.
Pushing a tag `vX.Y.Z` (must match `__version__` in `main.py`) additionally uploads the binary to the
package registry and creates a GitLab release.
