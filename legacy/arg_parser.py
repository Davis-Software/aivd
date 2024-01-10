import argparse


def parse_sys_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--find-offset-of', metavar='<audio file>', type=str, help='Find the offset of file',
                        required=True)
    parser.add_argument('--within', metavar='<folder>', type=str, help='Within files folder', default=".")
    parser.add_argument("--recursive", metavar="<boolean>", type=bool, default=False,
                        help="Recursively search for files in the within folder")
    parser.add_argument('--extension', metavar='<file extension>', type=str, default="*",
                        help='File with the extension to use')
    parser.add_argument("--extension-skip", metavar="<file extension>", type=str, default="",
                        help="File with the extension to skip")
    parser.add_argument('--window', metavar='<seconds>', type=int, default=60,
                        help='Only use first n seconds of a target audio')
    parser.add_argument("--log-level", metavar="<level>", type=str, default="info",
                        help="Log Level: debug, info, warning, error")
    parser.add_argument("--raw", metavar="<boolean>", type=bool, default=False,
                        help="Displays the result as raw json data instead of formatting it")
    parser.add_argument("--ffmpeg", metavar="<path>", type=str, default="/usr/bin/ffmpeg",
                        help="FFMPEG path")

    return parser.parse_args()
