"""Test signals."""

from __future__ import annotations

import os
import signal

import pytest

from pyshell_lab import signals

POSIX = os.name != "nt"


@pytest.mark.skipif(not POSIX, reason="signal tests require POSIX")
def test_install_shell_signal_handlers_sets_sigint() -> None:
    previous = signal.getsignal(signal.SIGINT)
    try:
        signals.install_shell_signal_handlers()
        assert signal.getsignal(signal.SIGINT) is signals._handle_sigint
    finally:
        signal.signal(signal.SIGINT, previous)


@pytest.mark.skipif(not POSIX, reason="signal tests require POSIX")
def test_ignore_and_restore_sigint_round_trip() -> None:
    previous = signal.getsignal(signal.SIGINT)
    try:
        signals.install_shell_signal_handlers()
        saved = signals.ignore_sigint_in_parent()
        assert signal.getsignal(signal.SIGINT) is signal.SIG_IGN
        signals.restore_sigint_in_parent(saved)
        assert signal.getsignal(signal.SIGINT) is signals._handle_sigint
    finally:
        signal.signal(signal.SIGINT, previous)


@pytest.mark.skipif(not POSIX, reason="signal tests require POSIX")
def test_restore_default_child_signals_restores_sigint() -> None:
    previous = signal.getsignal(signal.SIGINT)
    try:
        signals.install_shell_signal_handlers()
        signals.restore_default_child_signals()
        assert signal.getsignal(signal.SIGINT) is signal.SIG_DFL
    finally:
        signal.signal(signal.SIGINT, previous)


def test_ignore_sigint_is_noop_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    assert signals.ignore_sigint_in_parent() is signals._UNCHANGED
    signals.restore_sigint_in_parent(signals._UNCHANGED)


@pytest.mark.skipif(not POSIX, reason="signal tests require POSIX")
def test_wait_for_pids_ignores_sigint_while_foreground(monkeypatch) -> None:
    from pyshell_lab.executor import _wait_for_pids

    calls: list[str] = []

    def fake_ignore() -> object:
        calls.append("ignore")
        return object()

    def fake_restore(_previous: object) -> None:
        calls.append("restore")

    monkeypatch.setattr(signals, "ignore_sigint_in_parent", fake_ignore)
    monkeypatch.setattr(signals, "restore_sigint_in_parent", fake_restore)

    pid = os.fork()
    if pid == 0:
        os._exit(0)
    assert _wait_for_pids([pid], foreground=True) == 0
    assert calls == ["ignore", "restore"]
