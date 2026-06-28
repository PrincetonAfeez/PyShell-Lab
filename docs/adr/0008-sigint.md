# ADR 0008: Keep Foreground Jobs In The Shell's Process Group For Ctrl-C

## Status

Accepted (supersedes the earlier "forward SIGINT to the foreground group" approach)

## Context

Ctrl-C should interrupt the running foreground command, not kill the interactive shell. A shell normally gives each job its own process group and hands the terminal to the foreground group with `tcsetpgrp`. This project defers `tcsetpgrp` (see ADR 0010).

Putting a foreground job in its own process group *without* `tcsetpgrp` is actively harmful: the job becomes a background process group from the terminal's point of view, so any program that reads the terminal (`cat`, `grep`, a REPL) receives `SIGTTIN` and stops, hanging the shell in `waitpid`.

## Decision

Foreground jobs run in the shell's own process group, which is the terminal's foreground process group. Children restore the default SIGINT disposition before `exec`, so a terminal Ctrl-C is delivered to the foreground child directly. While the shell waits for a foreground job it temporarily sets SIGINT to `SIG_IGN`, so the shell is not interrupted. At the prompt, the shell's SIGINT handler raises `KeyboardInterrupt`, which the REPL catches to abandon the current line.

Background jobs and background pipelines get their own process group so signals can target the whole job.

## Consequences

The shell stays alive after Ctrl-C, and foreground programs that read the terminal work correctly. Full terminal ownership transfer is still deferred to advanced job control, at which point foreground jobs can move to their own groups with `tcsetpgrp`.
