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
* currently works on linux only
* `python3.5 - python3.7` only (scipy)
* `ffmpeg` is required
* development requirements can be installed with `pip3 install -r requirements.txt`

### Usage
```shell
    aivd [OPTIONS] INPUT_FILE DIRECTORY

        Find the INPUT_FILE audio file in the specified video or audio files in a
        folder and return the time index.
        
        INPUT_FILE: The audio file to search for.
        DIRECTORY: The directory with the video or audio files to search in.
```

| Option              | Data Type            | Description                                                                         | Default                                        |
|---------------------|----------------------|-------------------------------------------------------------------------------------|------------------------------------------------|
| `-r`, `--recursive` | flag                 | Search recursively in the specified directory.                                      |                                                |
| `-e`, `--extension` | `string`             | The extension of the video/audio files to search in. Can be a comma separated list. | `mp4,mkv,avi,mov,wmv,mp3,wav,flac,ogg,m4a,wma` |
| `-x`, `--exclude`   | `string`             | Exclude the specified extension from the search. Can be a comma separated list.     | `""`                                           |
| `-t`, `--time`      | `integer`            | How many seconds of the input audio file to search for.                             | `-1` (meaning the entire file)                 |
| `-w`, `--window`    | `integer`            | The window size in seconds to search for the audio file.                            | `60`                                           |
| `-f`, `--format`    | `json \| txt \| raw` | The output format.                                                                  | `"txt"`                                        |
| `-c`, `--threads`   | `integer`            | The number of CPU threads to use.                                                   | half of system cpu threads                     |
| `--ffmpeg`          | `string`             | The path to the ffmpeg executable.                                                  | from system path                               |
| `--no-clean`        | flag                 | Do not clean up temporary files.                                                    |                                                |
| `--silent`          | flag                 | Do not print anything but the final output to the console.                          |                                                |
| `--debug`           | flag                 | Print debug information to the console.                                             |                                                |
| `--dry-run`         | flag                 | Do not run the program, just print the parameters.                                  |                                                |
| `--version`         | flag                 | Print the version number and exit.                                                  |                                                |
| `--legacy`          | flag                 | Use the legacy cli.                                                                 |                                                |
| `--help`            | flag                 | Show help message and exit.                                                         |                                                |

### Legacy CLI
```shell
    aivd --legacy [-h] --find-offset-of <audio file> [--within <folder>]
            [--extension <file extension>] [--recursive <boolean>]
            [--extension-skip <file extension>] [--window <seconds>]
            [--log-level <level>] [--raw <boolean>] [--ffmpeg <path>]
```

| Option                             | Type      | Description                                     | Default             | Required |
|------------------------------------|-----------|-------------------------------------------------|---------------------|----------|
| `--legacy`                         | flag      | Needed to use the legacy cli                    |                     | yes      |
| `-h` or `--help`                   | flag      | Display the help dialog                         |                     | no       |
| `--find-offset-of <audio file>`    | `string`  | Audio file to search for                        |                     | yes      |
| `--within <folder>`                | `string`  | Folder path with video files to search in       | `"."`               | no       |
| `--recursive <boolean>`            | `boolean` | Recursively traverse specified folder           | `false`             | no       |
| `--extension <ile extension>`      | `string`  | Only search in the files with this extension    | `"*"`               | no       |
| `--extension-skip <ile extension>` | `string`  | Skip the files with this extension              | `""`                | no       |
| `--window <seconds>`               | `integer` | Only search in the first n seconds of the files | `60`                | no       |
| `--log-level <log level>`          | `string`  | Set the applications log level                  | `"info"`            | no       |
| `--raw <boolean>`                  | `boolean` | Set raw output (as JSON)                        | `false`             | no       |
| `--ffmpeg <path>`                  | `string`  | Path to a custom ffmpeg installation            | `"/usr/bin/ffmpeg"` | no       |

### Compilation
You can use pyinstaller to generate a binary in `./dist/`
```shell
    pyinstaller aivd.spec
```
