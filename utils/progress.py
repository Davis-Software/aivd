import os
import json

import click

from colorama import Fore, Style


class Progress:
    """
    Progress updates on stderr, so stdout only ever contains the final result.

    As JSON there is one object per line:
        {"type": "start", "total": 24}
        {"type": "progress", "done": 3, "total": 24, "file": "...", "result": {...}}
        {"type": "warning" | "error", "message": "..."}
        {"type": "done", "total": 24, "found": 20, "not_found": 3, "failed": 1}
    Otherwise it prints one short line per finished file.
    """

    def __init__(self, enabled=False, as_json=False):
        self.enabled = enabled
        self.as_json = enabled and as_json
        self.total = 0
        self.done = 0

    def emit(self, event):
        click.echo(json.dumps(event), err=True)  # click.echo flushes, so readers see every line immediately

    def message(self, level, message):
        self.emit({"type": level, "message": message.strip()})

    def start(self, total):
        self.total = total
        self.done = 0
        if not self.enabled:
            return
        if self.as_json:
            self.emit({"type": "start", "total": total})
        else:
            click.echo(f"{Fore.WHITE}[{Fore.CYAN}0/{total}{Fore.WHITE}] Searching {total} files...{Style.RESET_ALL}",
                       err=True)

    def file_done(self, file, result):
        self.done += 1
        if not self.enabled:
            return
        if self.as_json:
            self.emit({"type": "progress", "done": self.done, "total": self.total, "file": file, "result": result})
            return

        if result["error"] is not None:
            summary = f"{Fore.RED}error"
        elif result["found"]:
            summary = f"{Fore.GREEN}{result['offset']}s"
        else:
            summary = f"{Fore.YELLOW}not found"
        click.echo(f"{Fore.WHITE}[{Fore.CYAN}{self.done}/{self.total}{Fore.WHITE}] {Fore.RESET}"
                   f"{os.path.basename(file)}: {summary}{Style.RESET_ALL}", err=True)

    def finish(self, results):
        if not self.as_json:
            return
        values = list(results.values())
        failed = sum(1 for r in values if r["error"] is not None)
        found = sum(1 for r in values if r["found"])
        self.emit({"type": "done", "total": len(values), "found": found, "not_found": len(values) - found - failed,
                   "failed": failed})
