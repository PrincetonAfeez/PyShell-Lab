"""Test jobs."""

from __future__ import annotations

import os

import pytest

from pyshell_lab.jobs import JobStatus, JobTable, decode_wait_status

POSIX = os.name != "nt" and hasattr(os, "fork")


def test_pipeline_job_reported_once_when_all_pids_finish() -> None:
    table = JobTable()
    job = table.add("a | b", [10, 11], pgid=10)

    # First stage exits: the job is not yet finished, so it is not reported.
    assert table.mark_pid_done(10, 0) is None
    assert job.status == JobStatus.RUNNING

    # Last stage exits: now the job transitions to done and is returned once.
    finished = table.mark_pid_done(11, 0)
    assert finished is job
    assert job.status == JobStatus.DONE
    assert job.exit_status == 0


def test_pipeline_uses_last_stage_exit_status() -> None:
    table = JobTable()
    job = table.add("a | b", [10, 11], pgid=10)  # last stage is pid 11
    # Last stage finishes first (status 0); first stage finishes last (status 3).
    assert table.mark_pid_done(11, 0) is None
    finished = table.mark_pid_done(10, 3)
    assert finished is job
    assert job.exit_status == 0  # last stage's status, not the last-reaped 3
    assert job.status == JobStatus.DONE


def test_failed_job_status() -> None:
    table = JobTable()
    job = table.add("false-cmd", [20], pgid=20)
    finished = table.mark_pid_done(20, 1)
    assert finished is job
    assert job.status == JobStatus.FAILED
    assert job.exit_status == 1


def test_remove_drops_job() -> None:
    table = JobTable()
    job = table.add("sleep 1", [30], pgid=30)
    assert table.all()
    table.remove(job.job_id)
    assert table.all() == []


@pytest.mark.skipif(not POSIX, reason="wait-status decoding uses POSIX os.W* helpers")
def test_decode_wait_status_signal() -> None:
    # A clean exit code 3 encodes as 3 << 8 in the wait status word.
    assert decode_wait_status(3 << 8) == 3
    # Termination by signal N (low 7 bits) is reported as 128 + N.
    assert decode_wait_status(9) == 128 + 9
