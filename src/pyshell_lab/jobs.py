"""Background job table and child reaping helpers."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import StrEnum


class JobStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    job_id: int
    command_line: str
    status: JobStatus
    pids: list[int]
    pgid: int | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    exit_status: int | None = None
    last_pid: int | None = None
    statuses: dict[int, int] = field(default_factory=dict)


@dataclass
class JobTable:
    jobs: dict[int, Job] = field(default_factory=dict)
    _next_id: int = 1

    def add(self, command_line: str, pids: list[int], pgid: int | None = None) -> Job:
        pid_list = list(pids)
        job = Job(
            self._next_id,
            command_line,
            JobStatus.RUNNING,
            pid_list,
            pgid,
            last_pid=pid_list[-1] if pid_list else None,
        )
        self.jobs[job.job_id] = job
        self._next_id += 1
        return job

    def all(self) -> list[Job]:
        return list(self.jobs.values())

    def remove(self, job_id: int) -> None:
        self.jobs.pop(job_id, None)

    def mark_pid_done(self, pid: int, exit_status: int) -> Job | None:
        """Record that ``pid`` exited. Returns the job only when every pid in it
        has finished, so a multi-stage pipeline is reported exactly once. The
        job's exit status is the last stage's, matching the pipeline rule."""

        for job in self.jobs.values():
            if pid in job.pids and job.status == JobStatus.RUNNING:
                job.statuses[pid] = exit_status
                job.pids.remove(pid)
                if not job.pids:
                    final = (
                        exit_status
                        if job.last_pid is None
                        else job.statuses.get(job.last_pid, exit_status)
                    )
                    job.status = JobStatus.DONE if final == 0 else JobStatus.FAILED
                    job.exit_status = final
                    job.end_time = time.time()
                    return job
                return None
        return None

    def reap_finished(self) -> list[Job]:
        if os.name == "nt" or not hasattr(os, "waitpid"):
            return []

        finished: list[Job] = []
        while True:
            try:
                pid, status_word = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            except OSError:
                break
            if pid == 0:
                break
            job = self.mark_pid_done(pid, decode_wait_status(status_word))
            if job is not None:
                finished.append(job)
        return finished


def format_job_line(job: Job) -> str:
    return f"[{job.job_id}] {job.status.value:8s} {job.command_line}"


def decode_wait_status(status_word: int) -> int:
    # Only exited/signaled statuses are reachable: nothing waits with WUNTRACED
    # and children ignore SIGTSTP, so a stopped status never reaches here.
    if os.WIFEXITED(status_word):
        return os.WEXITSTATUS(status_word)
    if os.WIFSIGNALED(status_word):
        return 128 + os.WTERMSIG(status_word)
    return 1
