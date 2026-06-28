"""Test jobs extra."""

from __future__ import annotations

import os

import pytest

from pyshell_lab.jobs import JobStatus, JobTable, decode_wait_status, format_job_line


def test_mark_pid_done_unknown_pid_returns_none() -> None:
    table = JobTable()
    table.add("job", [1], pgid=1)
    assert table.mark_pid_done(999, 0) is None


def test_mark_pid_done_single_pid_no_last_pid() -> None:
    table = JobTable()
    job = table.add("solo", [5], pgid=5)
    job.last_pid = None
    finished = table.mark_pid_done(5, 2)
    assert finished is job
    assert job.exit_status == 2
    assert job.status == JobStatus.FAILED


def test_job_ids_increment() -> None:
    table = JobTable()
    first = table.add("a", [1], pgid=1)
    second = table.add("b", [2], pgid=2)
    assert second.job_id == first.job_id + 1


def test_format_job_line_failed() -> None:
    job = JobTable().add("false", [1], pgid=1)
    job.status = JobStatus.FAILED
    assert "failed" in format_job_line(job)


def test_reap_finished_returns_empty_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    assert JobTable().reap_finished() == []


def test_decode_wait_status_unknown_returns_one() -> None:
    if not hasattr(os, "WIFEXITED"):
        pytest.skip("wait status macros require POSIX")
    assert decode_wait_status(0) == 1
