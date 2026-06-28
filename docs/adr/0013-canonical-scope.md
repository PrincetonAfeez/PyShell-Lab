# ADR 0013: Canonical Scope And Execution API

## Status

Accepted

## Context

The repository contains two scope documents: `shell_scope.txt` (the original brief) and `revised_pyshell_lab_scope.txt` (a later revision). They disagree on a few classifications, which could confuse a reviewer:

- `shell_scope.txt` lists glob expansion and `fg`/`bg`/Ctrl-Z as `[CORE]`.
- `revised_pyshell_lab_scope.txt` moves glob to `[STRETCH]` and `fg`/`bg`/Ctrl-Z to `[ADVANCED]`.
- Both scope briefs mention `os.execvp`, while the implementation uses `os.execvpe`.

## Decision

`revised_pyshell_lab_scope.txt` is the canonical scope. Glob expansion is stretch, and full job control (`fg`, `bg`, Ctrl-Z, `tcsetpgrp`) is advanced and deferred (see ADR 0010).

External commands are executed with `os.execvpe` rather than `os.execvp` so the child's environment is passed explicitly from `ShellState` (exported variables plus any per-command assignments) instead of inherited implicitly. `execvpe` keeps the same PATH-search behavior as `execvp`.

## Consequences

The capstone is graded against the revised scope. `shell_scope.txt` is retained for history only. The `execvpe` choice makes environment hand-off to children explicit and testable.
