# ADR 0010: Defer Full Terminal Job Control

## Status

Accepted

## Context

Full `fg`, `bg`, Ctrl-Z, and `tcsetpgrp` behavior requires careful terminal foreground ownership and pseudo-terminal testing.

## Decision

The current version implements background process groups, signal-correct Ctrl-C handling (see ADR 0008), background jobs, and reaping. Full terminal job control is deferred.

Because `tcsetpgrp` is deferred, foreground jobs stay in the shell's process group rather than each getting their own; otherwise a foreground program that reads the terminal would be stopped by `SIGTTIN`. Moving foreground jobs into their own groups is part of the deferred terminal-control work.

For the same reason the shell ignores the stop signals `SIGTSTP`, `SIGTTIN`, and `SIGTTOU` (children inherit this), so Ctrl-Z is a no-op instead of suspending the shell or blocking it on a stopped child. Suspend/resume is part of the deferred work.

## Consequences

The core systems learning goals are covered without making the first version fragile. The trade-off is documented so the missing `tcsetpgrp` step is explicit rather than accidental.
