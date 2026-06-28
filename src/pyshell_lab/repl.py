"""Interactive and script-mode shell loops."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from . import config, history, signals
from .errors import ExecutionError, LexerError, ParserError, ShellError, ShellExit
from .executor import execute
from .jobs import format_job_line
from .parser import parse_line
from .state import ShellState


class Shell:
    def __init__(self, state: ShellState | None = None) -> None:
        self.state = state or ShellState()

    def run_interactive(self, *, load_rc: bool = True) -> int:
        signals.install_shell_signal_handlers()
        history.load_history(self.state)
        if load_rc:
            try:
                self._load_rc()
            except ShellExit as exc:
                return exc.status & 0xFF

        status = self.state.last_status
        try:
            while True:
                # The whole loop body is guarded so a stray Ctrl-C or an
                # unexpected error never crashes the shell with a traceback.
                try:
                    self._report_finished_jobs()
                    try:
                        line = input(self.prompt())
                    except EOFError:
                        print()
                        break
                    try:
                        status = self.execute_line(line)
                    except ShellExit as exc:
                        status = exc.status
                        break
                except KeyboardInterrupt:
                    print()
                    self.state.last_status = status = 130
                except (OSError, RuntimeError) as exc:
                    print(f"pyshell: internal error: {exc}", file=sys.stderr)
                    self.state.last_status = status = 1
                except Exception as exc:
                    print(f"pyshell: internal error: {exc}", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
                    self.state.last_status = status = 1
        finally:
            history.save_history(self.state)
        return status

    def run_script(self, script: Path, *, load_rc: bool = True) -> int:
        signals.install_shell_signal_handlers()
        if load_rc:
            try:
                self._load_rc()
            except ShellExit as exc:
                return exc.status & 0xFF

        status = 0
        try:
            lines = script.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            print(f"pyshell: {script}: {exc.strerror}", file=sys.stderr)
            return 1

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                status = self.execute_line(line, remember=False)
            except ShellExit as exc:
                return exc.status & 0xFF
            except KeyboardInterrupt:
                print()
                return 130
            except (OSError, RuntimeError) as exc:
                print(f"pyshell: internal error: {exc}", file=sys.stderr)
                status = 1
            except Exception as exc:
                print(f"pyshell: internal error: {exc}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                status = 1
            self._report_finished_jobs()
        return status

    def _load_rc(self) -> None:
        config.run_rc_file(self.state, lambda line: self.execute_line(line, remember=False))

    def execute_line(self, line: str, *, remember: bool = True) -> int:
        stripped = line.strip()
        if not stripped:
            return self.state.last_status
        if remember:
            history.remember(self.state, line)

        try:
            node = parse_line(line)
            return execute(node, self.state, line)
        except ExecutionError as exc:
            print(f"pyshell: {exc}", file=sys.stderr)
            self.state.last_status = 1
            return 1
        except (LexerError, ParserError, ShellError) as exc:
            print(f"pyshell: {exc}", file=sys.stderr)
            self.state.last_status = 2
            return 2
        except OSError as exc:
            # e.g. fork/pipe exhaustion: report instead of crashing the shell.
            print(f"pyshell: {exc}", file=sys.stderr)
            self.state.last_status = 1
            return 1

    def prompt(self) -> str:
        return f"pyshell[{self.state.last_status}] {self.state.cwd}$ "

    def _report_finished_jobs(self) -> None:
        for job in self.state.jobs.reap_finished():
            print(format_job_line(job))
            self.state.jobs.remove(job.job_id)
