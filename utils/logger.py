import click

from colorama import Fore, Style


class Logger:
    """
    Logs to stderr so stdout only ever contains the result.

    With `events` (JSON progress mode) stderr has to stay machine-readable: info and debug output is dropped,
    warnings and errors become JSON events.
    """

    def __init__(self, silent=False, debug=False, events=None):
        self._events = events
        self._silent = silent or events is not None
        self._debug = debug and events is None

    @property
    def is_silent(self):
        return self._silent

    @property
    def is_debug(self):
        return self._debug

    def echo(self, prefix, message, secondary_color=Fore.WHITE, prefix_color=Fore.CYAN, message_color=Fore.RESET):
        if not self._silent:
            click.echo(f"{secondary_color}[{prefix_color}{prefix}{secondary_color}] {message_color}{message}"
                       f"{Style.RESET_ALL}",
                       err=True)

    def error(self, message, trace=None):
        if self._events is not None:
            self._events.message("error", message)
            return
        self.echo("ERROR", message, secondary_color=Fore.YELLOW, prefix_color=Fore.RED, message_color=Fore.LIGHTRED_EX)
        if trace is not None and self._debug and not self._silent:
            click.echo(f"\t{Fore.WHITE}{trace}{Style.RESET_ALL}", err=True)

    def file_error(self, message):
        """An error about a single file. Not repeated as a JSON event, the file's progress event contains it."""
        if self._events is None:
            self.error(message)

    def warning(self, message):
        if self._events is not None:
            self._events.message("warning", message)
            return
        self.echo("WARNING", message, prefix_color=Fore.YELLOW, message_color=Fore.LIGHTYELLOW_EX)

    def info(self, message):
        self.echo("INFO", message)

    def debug(self, message):
        if self._debug:
            self.echo("DEBUG", message, secondary_color=Fore.WHITE, prefix_color=Fore.BLUE,
                      message_color=Fore.LIGHTBLUE_EX)

    def empty_line(self, debug_only=True):
        if self._debug and debug_only and not self._silent:
            click.echo("", err=True)
