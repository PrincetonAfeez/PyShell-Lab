"""Command-line entry point for PyShell Lab."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .repl import Shell


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyshell", description="Educational POSIX shell")
    parser.add_argument("script", nargs="?", help="optional .psh script to execute")
    parser.add_argument("--no-rc", action="store_true", help="do not read ~/.pyshellrc")
    parser.add_argument("--version", action="version", version=f"pyshell {__version__}")
    args = parser.parse_args(argv)

    shell = Shell()
    if args.script:
        return shell.run_script(Path(args.script), load_rc=not args.no_rc)
    return shell.run_interactive(load_rc=not args.no_rc)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
