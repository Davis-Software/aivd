import click

from colorama import Fore, Style


class Logger:
    def __init__(self, silent=False, debug=False):
        self._silent = silent
        self._debug = debug

    @property
    def is_silent(self):
        return self._silent

    @property
    def is_debug(self):
        return self._debug

    def echo(self, prefix, message, secondary_color=Fore.WHITE, prefix_color=Fore.CYAN, message_color=Fore.RESET,
             err=False):
        if not self._silent:
            click.echo(f"{secondary_color}[{prefix_color}{prefix}{secondary_color}] {message_color}{message}"
                       f"{Style.RESET_ALL}",
                       err=err)

    def error(self, message, trace=None):
        self.echo("ERROR", message, secondary_color=Fore.YELLOW, prefix_color=Fore.RED, message_color=Fore.LIGHTRED_EX,
                  err=True)
        if trace is not None and self._debug and not self._silent:
            click.echo(f"\t{Fore.WHITE}{trace}{Style.RESET_ALL}", err=True)

    def info(self, message):
        self.echo("INFO", message)

    def debug(self, message):
        if self._debug:
            self.echo("DEBUG", message, secondary_color=Fore.WHITE, prefix_color=Fore.BLUE,
                      message_color=Fore.LIGHTBLUE_EX)

    def empty_line(self, debug_only=True):
        if self._debug and debug_only and not self._silent:
            click.echo("")
