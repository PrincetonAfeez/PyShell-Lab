"""Signal helpers for interactive Ctrl-C handling.

The shell keeps foreground jobs in its own process group (the terminal's
foreground process group) because full terminal hand-off with ``tcsetpgrp`` is
deferred. A terminal-generated Ctrl-C is therefore delivered to the foreground
child directly, which restores the default SIGINT disposition before ``exec``.
While the shell waits for that child it temporarily *ignores* SIGINT so the
signal interrupts the child, not the shell. At the prompt (no foreground job)
SIGINT instead raises ``KeyboardInterrupt`` so the REPL can abandon the line.

Because job control (Ctrl-Z, fg, bg) is deferred, the shell also ignores the
job-control stop signals (SIGTSTP/SIGTTIN/SIGTTOU). Foreground children inherit
that disposition, so Ctrl-Z is a no-op rather than something that would suspend
the shell itself or leave it blocked on a stopped child.
"""

from __future__ import annotations

import os
import signal
from typing import Any

# Distinguishes "we did not change the handler" from "the previous handler was
# None", so a real handler is always restored.
_UNCHANGED = object()

_JOB_CONTROL_SIGNALS = ("SIGTSTP", "SIGTTIN", "SIGTTOU")


def install_shell_signal_handlers() -> None:
    if os.name == "nt":
        return
    signal.signal(signal.SIGINT, _handle_sigint)
    for name in _JOB_CONTROL_SIGNALS:
        signum = getattr(signal, name, None)
        if signum is not None:
            signal.signal(signum, signal.SIG_IGN)


def restore_default_child_signals() -> None:
    if os.name == "nt":
        return
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    if hasattr(signal, "SIGQUIT"):
        signal.signal(signal.SIGQUIT, signal.SIG_DFL)
    # SIGTSTP/SIGTTIN/SIGTTOU stay ignored (inherited from the shell) so the
    # child cannot be stopped while job control is deferred.


def ignore_sigint_in_parent() -> Any:
    """Ignore SIGINT in the shell while a foreground job owns the terminal.

    Returns the previous handler so it can be restored once the job finishes,
    or ``_UNCHANGED`` if nothing was changed.
    """

    if os.name == "nt":
        return _UNCHANGED
    try:
        return signal.signal(signal.SIGINT, signal.SIG_IGN)
    except ValueError:
        # signal.signal only works in the main thread (e.g. some test runners).
        return _UNCHANGED


def restore_sigint_in_parent(previous: Any) -> None:
    if previous is _UNCHANGED or previous is None:
        return
    try:
        signal.signal(signal.SIGINT, previous)
    except (ValueError, TypeError):
        pass


def _handle_sigint(signum: int, frame: object) -> None:
    # Reached only at the interactive prompt: the shell ignores SIGINT while a
    # foreground job runs. Raising lets the REPL discard the current input line.
    raise KeyboardInterrupt
