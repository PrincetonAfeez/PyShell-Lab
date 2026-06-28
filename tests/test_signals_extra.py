"""Test signals extra."""

from __future__ import annotations

import os
import signal

import pytest

from pyshell_lab import signals


def test_install_shell_signal_handlers_noop_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    previous = signal.getsignal(signal.SIGINT)
    signals.install_shell_signal_handlers()
    assert signal.getsignal(signal.SIGINT) is previous


def test_restore_default_child_signals_noop_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    signals.restore_default_child_signals()


def test_handle_sigint_raises_keyboard_interrupt() -> None:
    with pytest.raises(KeyboardInterrupt):
        signals._handle_sigint(signal.SIGINT, None)


def test_restore_sigint_with_none_is_noop() -> None:
    signals.restore_sigint_in_parent(None)


@pytest.mark.skipif(os.name == "nt", reason="job-control signals are POSIX-only")
def test_install_ignores_job_control_signals() -> None:
    previous = {
        name: signal.getsignal(getattr(signal, name)) for name in ("SIGTSTP", "SIGTTIN", "SIGTTOU")
    }
    try:
        signals.install_shell_signal_handlers()
        for name in ("SIGTSTP", "SIGTTIN", "SIGTTOU"):
            assert signal.getsignal(getattr(signal, name)) is signal.SIG_IGN
    finally:
        for name, handler in previous.items():
            signal.signal(getattr(signal, name), handler)


@pytest.mark.skipif(os.name == "nt", reason="SIGQUIT restore is POSIX-only")
def test_restore_default_child_signals_restores_sigquit() -> None:
    if not hasattr(signal, "SIGQUIT"):
        pytest.skip("SIGQUIT unavailable")
    previous = signal.getsignal(signal.SIGQUIT)
    try:
        signals.restore_default_child_signals()
        assert signal.getsignal(signal.SIGQUIT) is signal.SIG_DFL
    finally:
        signal.signal(signal.SIGQUIT, previous)
