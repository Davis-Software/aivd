# Audio-In-Video-Detector AIVD

> Developed by [Davis_Software](https://github.com/Davis-Software) &copy; 2023

![GitHub release (latest by date)](https://img.shields.io/github/v/release/Davis-Software/aivd?style=for-the-badge)
![GitHub issues](https://img.shields.io/github/issues-raw/Davis-Software/aivd?style=for-the-badge)
![GitHub closed issues](https://img.shields.io/github/issues-closed/Davis-Software/aivd?style=for-the-badge)
![GitHub all releases](https://img.shields.io/github/downloads/Davis-Software/aivd/total?style=for-the-badge)
![GitHub](https://img.shields.io/github/license/Davis-Software/aivd?style=for-the-badge)

### What is AIVD?
AIVD or Audio-In-Video-Detector finds a specified audio file in the audio track
of video files and returns the audio offset

It can be thus for example be used to find the intro of a tv show in its episodes

### Requirements
* currently works on linux only
* `python3.5 - python3.7` only (scipy)
* `ffmpeg` is required
* development requirements can be installed with `pip3 install -r requirements.txt`

### Usage
```shell
    aivd [-h] [--find-offset-of <audio file>] [--within <folder>]
            [--extension <file extension>] [--window <seconds>]
            [--log-level <level>] [--raw <boolean>] [--ffmpeg <path>]
```

| Option                          | Type      | Description                                     | Default             | Required |
|---------------------------------|-----------|-------------------------------------------------|---------------------|----------|
| `-h` or `--help`                | flag      | Display the help dialog                         |                     | no       |
| `--find-offset-of <audio file>` | `string`  | Audio file to search for                        |                     | yes      |
| `--within <folder>`             | `string`  | Folder path with video files to search in       | `.`                 | no       |
| `--extension <ile extension>`   | `string`  | Only search in the files with this extension    | `*`                 | no       |
| `--window <seconds>`            | `integer` | Only search in the first n seconds of the files | `60`                | no       |
| `--log-level <log level>`       | `string`  | Set the applications log level                  | `"info"`            | no       |
| `--raw <boolean>`               | `boolean` | Set raw output (as JSON)                        | `false`             | no       |
| `--ffmpeg <path>`               | `string`  | Path to a custom ffmpeg installation            | `"/usr/bin/ffmpeg"` | no       |

### Compilation
You can use pyinstaller to generate a binary in `./dist/`
```shell
    pyinstaller aivd.spec
```
