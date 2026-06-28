# ADR 0003: Do Not Use subprocess.run As The Engine

## Status

Accepted

## Context

`subprocess.run` would hide the low-level process mechanics that the project is meant to teach.

## Decision

External command execution uses `os.fork`, `os.execvpe`, `os.waitpid`, `os.pipe`, and `os.dup2`.

## Consequences

The code is more explicit and platform-specific, but students can trace the exact handoff from shell process to child process.
