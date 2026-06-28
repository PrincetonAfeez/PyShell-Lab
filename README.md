# PyShell Lab

[![CI](https://github.com/PrincetonAfeez/pyshell-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/PrincetonAfeez/pyshell-lab/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

PyShell Lab is an educational POSIX-style shell written in Python. It is a systems programming capstone, not a Bash clone. The project is deliberately CLI-only and focuses on the path from command text to real child processes.

The shell demonstrates:

- quote-aware lexing
- structured parsing into command data objects
- variable and tilde expansion
- builtins that mutate shell state
- external command execution through `fork`, `execvpe`, and `waitpid`
- redirection with `open` and `dup2`
- pipelines with `pipe`, `fork`, `dup2`, and descriptor cleanup
- basic background jobs and reaping
- Ctrl-C handling that interrupts the foreground job, not the shell

## Design Highlights

PyShell Lab is structured as a teaching shell, not a compatibility layer:

- **Separated pipeline:** lexer → parser → expansion → executor, with explicit AST dataclasses (ADR 0004)
- **Real process control:** external commands via `fork` / `execvpe` / `waitpid`, not `subprocess.run` (ADR 0003)
- **Stateful builtins in the parent:** `cd`, `export`, and friends mutate shell state where required (ADR 0005)
- **Documented trade-offs:** foreground jobs stay in the shell process group for Ctrl-C (ADR 0008); full job control is deferred (ADR 0010)
- **Tested core scope:** lexer through executor, POSIX-gated integration tests, CI coverage gate on Linux and macOS

## Platform

PyShell Lab targets POSIX platforms:

- Linux
- macOS
- Windows through WSL

Native Windows is not a full target because `os.fork`, POSIX process groups, and shell-style signal behavior are not available there. Lexer, parser, expansion, and most builtin tests still run on native Windows.

## Install And Run

```bash
python -m pip install -e ".[dev]"
pyshell
```

Run a script (loads `~/.pyshellrc` first, like interactive mode):

```bash
pyshell script.psh
pyshell --no-rc examples/demo.psh
```

Skip the optional startup file (interactive or script):

```bash
pyshell --no-rc
pyshell --no-rc script.psh
```

Run tests:

```bash
python -m pytest
```

On native Windows, POSIX execution tests are skipped. Run the suite in WSL to exercise `fork`, `exec`, redirection, and pipelines. The CI matrix includes Windows for lexer/parser/builtin coverage; **Linux and macOS jobs validate the full POSIX execution path**.

## Demo

```text
pyshell[0] /home/student$ echo hello | wc -c
6
pyshell[0] /home/student$ NAME=Ada
pyshell[0] /home/student$ echo "hi $NAME"
hi Ada
pyshell[0] /home/student$ ls /nope 2>&1 | wc -l
1
pyshell[0] /home/student$ false && echo skipped || echo recovered
recovered
pyshell[1] /home/student$ sleep 5 &
[1] 4123
pyshell[0] /home/student$ jobs
[1] running  sleep 5
pyshell[0] /home/student$ exit
```

The prompt shows the last exit status and the current directory.

A runnable version of this walkthrough lives in [`examples/demo.psh`](examples/demo.psh) (use `--no-rc` so startup does not alter the demo).

## Exit Status

| Situation | `$?` / return code |
|-----------|-------------------|
| Success | `0` |
| External command failure, redirect I/O error, fork/pipe failure | `1` |
| Lexer/parser/expansion error, builtin usage error | `2` |
| Command not found (`exec`) | `127` |
| Permission denied (`exec`) | `126` |
| Ctrl-C at interactive prompt | `130` |
| Signal-terminated child | `128 + signal` (e.g. SIGTERM → `143`) |

## Developing

```bash
python -m pip install -e ".[dev]"                  # flexible tool versions
python -m pip install -e . -r requirements-dev.txt # or the pinned, reproducible toolchain
python -m pytest --cov=pyshell_lab    # tests with coverage
ruff check . && ruff format --check .  # lint and format
mypy                                   # type-check (POSIX target)
```

The runtime has no third-party dependencies; `requirements-dev.txt` is a pinned
lockfile of the tooling only (CI uses it for deterministic linting).

## Project Layout

```text
examples/
  demo.psh      runnable walkthrough of core features
src/pyshell_lab/
  ast.py        structured command objects
  lexer.py      words, quotes, escapes, and operators
  parser.py     recursive-descent parser
  expansion.py  variable and tilde expansion
  executor.py   fork/exec/redirection/pipeline execution
  builtins.py   cd, pwd, export, jobs, type, which, and friends
  jobs.py       background job table and reaping
  signals.py    Ctrl-C forwarding
  history.py    in-memory and persisted history
  repl.py       interactive and script loops
  main.py       CLI entry point
```

## Command Flow

1. The REPL reads a line.
2. The lexer turns text into `WORD` and `OP` tokens while preserving quote context.
3. The parser builds `SimpleCommand`, `Pipeline`, `BackgroundCommand`, or `CommandSequence` objects.
4. Expansion turns command words into argument strings. Single quotes suppress expansion. Double quotes and unquoted words allow `$VAR`, `${VAR}`, `$?`, `$$`, and tilde expansion. Expanded values are not field-split, so `cmd "$VAR"` and `cmd $VAR` produce the same single argument (see Limitations).
5. The executor decides whether the command is a parent-process builtin or a child process.
6. External commands run through POSIX process primitives.

## Builtins

Implemented builtins:

- `cd`
- `pwd`
- `exit`
- `help`
- `echo`
- `export`
- `unset`
- `env`
- `set`
- `history`
- `jobs`
- `type`
- `which`

Some builtins must run in the shell process. `cd` cannot be implemented only by forking an external process because a child process cannot change the parent shell's current directory. `export` and `unset` also mutate shell state that future children inherit.

When a builtin appears in a pipeline or background job, it runs in a child process so it behaves like a pipeline stage and does not mutate the parent shell.

## Process Model

Foreground external commands use:

- `os.fork()` to create a child process
- `os.execvpe()` to replace the child with the target program
- `os.waitpid()` in the parent to collect the exit status

The child inherits the shell process state at fork time, including open file descriptors and environment values. After `exec`, the child process image is replaced by the requested program.

Exit status decoding handles normal exits and signal termination. Signal exits are reported as `128 + signal_number`, matching common shell convention.

## Redirection

Supported forms:

```bash
command > file      # stdout to file (truncate)
command >> file     # stdout to file (append)
command < file      # stdin from file
command 2> file     # stderr to file
command 2>&1        # stderr to wherever stdout currently points
command >&2         # stdout to wherever stderr currently points
command 2>&-        # close stderr
```

Redirection is applied with `os.open()` and `os.dup2()`; the `>&` forms duplicate one descriptor onto another with `os.dup2()` (or close it with `-`). Redirections are applied left to right, so `> file 2>&1` sends both streams to the file. For parent-process builtins, PyShell saves the original standard file descriptor with `os.dup()`, applies the redirect, runs the builtin, flushes output, and restores the original descriptor. If any redirection in the list fails, the already-applied ones are rolled back, so a failed redirect never permanently corrupts the shell's own `stdin`, `stdout`, or `stderr`.

## Pipes And File Descriptors

Pipelines use one `os.pipe()` pair between each stage. Every stage is forked before the parent waits, so pipeline commands run concurrently.

Each child duplicates only the pipe ends it needs:

- previous pipe read end to `stdin`
- next pipe write end to `stdout`

Then each child closes all pipe file descriptors. The parent also closes all pipe file descriptors after forking. This descriptor hygiene matters because a leaked write end can keep a pipe open forever and make the final reader hang.

Pipeline status is the exit status of the last command in the pipeline.

## Signals And Process Groups

Foreground jobs run in the shell's own process group, which is the terminal's foreground process group. A terminal-generated Ctrl-C is therefore delivered straight to the foreground child, which has restored the default SIGINT disposition before `exec`. While the shell waits for that child it temporarily ignores SIGINT, so the signal interrupts the child and the shell stays alive. At the prompt (no foreground job) SIGINT instead aborts the current input line and redraws the prompt.

This is a deliberate consequence of deferring terminal job control. Moving a foreground job into its *own* process group without also handing it the terminal via `tcsetpgrp` would make any program that reads the terminal (for example `cat`, `grep`, or a REPL) receive `SIGTTIN` and stop. Keeping foreground jobs in the shell's group avoids that until full job control is implemented.

Background jobs and background pipelines *do* get their own process group, so signals can target the whole job rather than a single child. Full terminal job control with `fg`, `bg`, Ctrl-Z, and `tcsetpgrp` is intentionally deferred.

Because that job control is deferred, the shell ignores the stop signals `SIGTSTP`, `SIGTTIN`, and `SIGTTOU`, and foreground children inherit that disposition. The effect is that Ctrl-Z is a deliberate no-op: it neither suspends the shell nor leaves it blocked on a stopped child. Suspend/resume arrives with the advanced job-control work.

## Variables And Assignment

```bash
NAME=value          # set a shell variable
NAME=$OTHER-suffix  # the value is expanded
export NAME=value   # set and export to child processes
NAME=value command  # assign only for that command's environment
```

A bare `NAME=value` word (unquoted name) assigns a shell variable in the shell process. When one or more assignments prefix a command, they apply only to that command: external commands receive them in their environment, and the assignments do not persist in the shell. As in POSIX shells, the assignment is not visible to the expansion of the same command line, so `FOO=bar echo $FOO` prints an empty value.

`set NAME=value` is also accepted as an explicit way to set a shell variable without exporting it, and `set` with no arguments lists shell variables.

An empty **expansion** is a no-op that succeeds and sets `$?` to `0`: a line that expands to nothing (such as an unset `$VAR` on its own) does nothing. A blank input line (no command text) also does nothing but **preserves** the previous `$?`. `cd` with an empty argument (`cd ""`) likewise does nothing. Redirections on an empty-expansion command still run (for example `$EMPTY > file` creates or truncates the file).

## Jobs

Background jobs use:

```bash
sleep 10 &
jobs
```

The shell returns to the prompt immediately, prints a job id and process group or PID, and stores metadata in the job table. Completed children are reaped before prompts and by the `jobs` builtin.

## History And Config

Interactive history is stored in memory and saved to:

```text
~/.pyshell_history
```

History is **interactive-only**: script mode does not read or write the history file.

If readline is available, basic line editing and recall are enabled through Python's standard `readline` module.

At startup, PyShell reads simple commands from:

```text
~/.pyshellrc
```

Both interactive mode and script mode load this file unless you pass `--no-rc`.

## Limitations

PyShell Lab intentionally does not implement:

- full Bash compatibility
- shell functions
- loops or conditionals beyond `&&`, `||`, and `;`
- field splitting of expanded values (an expanded `$VAR` stays one argument) and glob expansion
- shell variables visible to expansion (including `$PATH`) but not to external command lookup, `type`, or `which` until exported or passed as a prefix assignment — use `export PATH=…` or `PATH=… command` to affect child processes
- parameter-expansion modifiers (`${VAR:-default}`, `${VAR#prefix}`, ...) — only `$VAR`, `${VAR}`, `$?`, and `$$` are expanded
- positional parameters (`$1`, `$@`); `$0` is not the script name
- variable assignments as pipeline **stages** (`FOO=bar | ...` with no command on that stage); prefix assignments on the first stage of a pipeline (`FOO=bar cmd | ...`) are supported
- background `&` on a **compound sequence** as a whole (there are no subshells, so `(cmd1; cmd2) &` is not expressible); `&` applies only to the immediately preceding pipeline — in `echo a; echo b &`, only `echo b` runs in the background
- command substitution
- here-docs
- native Windows process control
- full terminal foreground job control
- custom cryptography

Comments are supported: a `#` that begins a word runs to end of line, so `echo hi # note` works while `echo a#b` keeps the `#` in the word.

The goal is to show how a shell turns text into structured commands and then into real OS-level process behavior.

## ADRs

Architecture decision records live in `docs/adr/`. A public scope summary is in [`docs/SCOPE.md`](docs/SCOPE.md).

| ADR | Topic |
|-----|--------|
| [0001](docs/adr/0001-cli-only.md) | CLI-only capstone |
| [0002](docs/adr/0002-posix-only.md) | POSIX platform target |
| [0003](docs/adr/0003-no-subprocess-run.md) | No `subprocess.run` engine |
| [0004](docs/adr/0004-separated-architecture.md) | Lexer / parser / expansion / executor split |
| [0005](docs/adr/0005-builtins-in-parent.md) | Stateful builtins in parent process |
| [0006](docs/adr/0006-pipelines.md) | Pipeline representation and execution |
| [0007](docs/adr/0007-redirection.md) | Redirection with fd save/restore |
| [0008](docs/adr/0008-sigint.md) | Ctrl-C and foreground process group |
| [0009](docs/adr/0009-background-jobs.md) | Background job table and reaping |
| [0010](docs/adr/0010-terminal-job-control-deferred.md) | Deferred fg/bg / Ctrl-Z |
| [0011](docs/adr/0011-execution-plan-deferred.md) | Deferred execution-plan debug |
| [0012](docs/adr/0012-audit-log-deferred.md) | Deferred audit log |
| [0013](docs/adr/0013-canonical-scope.md) | Canonical scope and `execvpe` |

## Repository

This project is intended to live in its own Git repository at [github.com/PrincetonAfeez/pyshell-lab](https://github.com/PrincetonAfeez/pyshell-lab) (update the README CI badge URL if you publish under a different name). If you keep it as a subdirectory of a larger monorepo, run CI and clone instructions from this `Shell/` directory so paths and badges stay correct.
