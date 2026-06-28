# PyShell Lab — Project Scope (Public Summary)

This document summarizes the **canonical capstone scope** for PyShell Lab. The full
grading brief lives in `revised_pyshell_lab_scope.txt` (local reference). See
[ADR 0013](adr/0013-canonical-scope.md) for scope precedence.

## Platform

- CLI-only educational POSIX shell (Python 3.11+)
- Targets Linux, macOS, and WSL — not native Windows process control

## Core features (implemented)

| Area | Scope |
|------|--------|
| Lexer / parser | Quote-aware words, operators, comments, recursive-descent AST |
| Expansion | `$VAR`, `${VAR}`, `$?`, `$$`, tilde on first unquoted part |
| Builtins | `cd`, `pwd`, `exit`, `help`, `echo`, `export`, `unset`, `env`, `set`, `history`, `jobs`, `type`, `which` |
| Execution | `fork`, `execvpe`, `waitpid` — no `subprocess.run` |
| Redirection | `>`, `>>`, `<`, `2>`, `2>&1`, `>&`, `2>&-` via `open` / `dup2` |
| Control flow | `;`, `&&`, `\|\|`, pipelines, background `&` |
| Jobs | Job table, non-blocking reap, `jobs` builtin |
| Signals | Ctrl-C at prompt; SIGINT ignored while waiting on foreground child |
| Config | `~/.pyshellrc` (interactive and script mode), `~/.pyshell_history` (interactive only), optional readline |

## Explicitly deferred (not required)

- Full Bash compatibility, glob expansion, aliases, functions
- Command substitution, here-docs, loops beyond `&&` / `\|\|`
- Field splitting after expansion
- Shell variables affect expansion but not external lookup until exported (see README Limitations)
- Parameter-expansion modifiers (`${VAR:-default}`, …)
- Positional parameters (`$1`, `$@`)
- Assignment-only **pipeline stages** (`FOO=bar \| …` as a stage with no command) — rejected at execution time
- Background `&` on a compound `;` sequence as a whole (no subshells); `&` binds to the preceding pipeline only (`echo a; echo b &` backgrounds just `echo b`)
- Full terminal job control: `fg`, `bg`, Ctrl-Z, `tcsetpgrp`
- Execution-plan debug mode, audit log, native Windows fork/exec

## Script and history semantics

- **Scripts** load `~/.pyshellrc` by default; use `--no-rc` to skip it (same flag as interactive mode).
- **History** (`~/.pyshell_history`) is loaded and saved only in interactive mode; script runs do not touch the file.

## Architecture decisions

- Separated lexer → parser → expansion → executor (ADR 0004)
- Parent-process builtins for state mutation (ADR 0005)
- Foreground jobs stay in the shell's process group (ADR 0008)
- Background pipelines get their own process group (ADR 0009)
- `execvpe` with explicit environment from `ShellState` (ADR 0013)

## Testing expectations

- Unit tests for lexer, parser, expansion, builtins, jobs
- POSIX-gated integration tests for fork/exec, redirection, pipelines, background jobs
- Signal handler install/restore tests (mocked where PTY tests are impractical)
- Full POSIX coverage validated on Linux/macOS CI agents; Windows runs parser/builtin tests only
