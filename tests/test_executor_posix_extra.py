"""Test executor POSIX extra."""

from __future__ import annotations

import os

import pytest

from pyshell_lab import signals
from pyshell_lab.executor import _cleanup_pipeline_children, _wait_for_pids

POSIX = os.name != "nt" and hasattr(os, "fork")


@pytest.mark.skipif(not POSIX, reason="requires POSIX waitpid")
def test_wait_for_pids_non_foreground_does_not_touch_sigint(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        signals,
        "ignore_sigint_in_parent",
        lambda: calls.append("ignore") or object(),
    )
    monkeypatch.setattr(signals, "restore_sigint_in_parent", lambda _p: calls.append("restore"))

    pid = os.fork()
    if pid == 0:
        os._exit(0)
    assert _wait_for_pids([pid], foreground=False) == 0
    assert calls == []


@pytest.mark.skipif(not POSIX, reason="requires POSIX signals")
def test_cleanup_pipeline_children_terminates_pids() -> None:
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    _cleanup_pipeline_children([pid])
    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)


@pytest.mark.skipif(not POSIX, reason="requires POSIX wait macros")
def test_reap_finished_collects_exited_child() -> None:
    from pyshell_lab.jobs import JobStatus, JobTable

    table = JobTable()
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    table.add("true", [pid], pgid=pid)
    finished = table.reap_finished()
    assert len(finished) == 1
    assert finished[0].status == JobStatus.DONE
