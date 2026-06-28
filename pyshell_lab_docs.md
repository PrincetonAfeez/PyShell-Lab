# Architecture Decision Record
## App — PyShell Lab
**Process Control Systems Group | Document 1 of 5**
**Status: Accepted**

---

## Context

The Process Control Systems group requires a portfolio-ready systems programming capstone that demonstrates how a shell turns user text into real operating-system process behavior. The project must show quote-aware lexing, parsing into structured command objects, expansion, parent-process builtins, POSIX process creation, redirection, pipelines, background jobs, signal handling, script mode, history, startup configuration, and a clean CLI entry point.

The project is named **PyShell Lab**. It is intentionally an educational POSIX-style shell, not a Bash clone and not a compatibility layer. It targets Linux, macOS, and Windows through WSL. Native Windows can run much of the lexer/parser/builtin test surface, but it is not a full execution target because `os.fork`, POSIX process groups, and Unix-style signal behavior are unavailable.

---

## Decisions

### Decision 1 — Build a CLI-only shell capstone

**Chosen:** Implement one command-line shell executable named `pyshell`.

**Rejected:** Building a GUI, web shell, terminal emulator, or remote shell service.

**Reason:** The learning goal is the shell pipeline itself: text input, parsing, expansion, process execution, and state mutation. A UI layer would distract from the operating-system primitives the project exists to demonstrate.

---

### Decision 2 — Target POSIX process primitives

**Chosen:** Use `os.fork()`, `os.execvpe()`, `os.waitpid()`, `os.pipe()`, `os.dup2()`, and POSIX signal handling for the execution path.

**Rejected:** Native Windows execution as a first-class target.

**Reason:** The project teaches Unix shell mechanics. Native Windows lacks the same fork/process-group/signal model, so claiming equivalent behavior would be misleading. Windows remains useful for lexer/parser/builtin tests where POSIX primitives are not required.

---

### Decision 3 — Do not use `subprocess.run` as the shell engine

**Chosen:** Implement external execution directly with `fork`, `execvpe`, and `waitpid`.

**Rejected:** Using `subprocess.run()` or `subprocess.Popen()` as the primary execution layer.

**Reason:** `subprocess` would hide the mechanics this capstone is designed to show. The project needs to demonstrate file descriptor setup, fork boundaries, child signal restoration, exec failure statuses, and wait status decoding.

---

### Decision 4 — Separate lexing, parsing, expansion, and execution

**Chosen:** Use an explicit pipeline:
```text
command text → lexer → parser → AST dataclasses → expansion → executor
```

**Rejected:** Interpreting text directly inside the executor.

**Reason:** Clear stages make the shell understandable and testable. The lexer preserves quote context. The parser creates command data objects. Expansion makes quote-sensitive word decisions. The executor only receives structured commands.

---

### Decision 5 — Preserve quote context in tokens

**Chosen:** Represent command words as `WordPart` objects with quote kind metadata.

**Rejected:** Collapsing all quote information during tokenization.

**Reason:** Expansion rules depend on quote context. Single quotes suppress expansion. Double quotes allow variable expansion but change backslash semantics. Unquoted text allows tilde expansion in leading position. Preserving this information avoids guesswork later.

---

### Decision 6 — Use dataclasses for the command AST

**Chosen:** Model commands with `SimpleCommand`, `Pipeline`, `BackgroundCommand`, `CommandSequence`, `Redirection`, and `CommandWord`.

**Rejected:** Passing nested lists or dictionaries between parser and executor.

**Reason:** Typed dataclasses make the intermediate representation explicit, easier to inspect, and easier to test.

---

### Decision 7 — Run stateful foreground builtins in the parent process

**Chosen:** `cd`, `export`, `unset`, `set`, `exit`, `jobs`, and similar builtins run in the parent when foreground and not inside a pipeline/background job.

**Rejected:** Forking every command, including all builtins.

**Reason:** Some builtins must mutate shell state. A child process cannot change the parent shell’s current directory or persistent environment.

---

### Decision 8 — Run builtins in children when used as pipeline/background stages

**Chosen:** Builtins inside pipelines or background jobs execute in child processes.

**Rejected:** Letting pipeline stages mutate parent shell state.

**Reason:** A pipeline stage behaves like a separate process. Running it in a child keeps shell state consistent and prevents a pipeline from unexpectedly changing the parent shell.

---

### Decision 9 — Apply redirection with save/restore for parent builtins

**Chosen:** Parent-process builtins save standard file descriptors with `os.dup()`, apply redirection with `os.open()` and `os.dup2()`, run the builtin, flush output, and restore the original descriptors.

**Rejected:** Skipping redirection for parent builtins or leaving descriptors modified.

**Reason:** `cd > file` and similar commands still need redirection semantics, but the shell must not permanently corrupt its own stdin/stdout/stderr.

---

### Decision 10 — Apply redirections left to right

**Chosen:** Redirections are applied in command order.

**Rejected:** Grouping redirection operations by target descriptor.

**Reason:** Shell redirection order matters. `> file 2>&1` and `2>&1 > file` mean different things.

---

### Decision 11 — Create all pipeline stages before waiting

**Chosen:** For pipelines, create the necessary pipes, fork every stage, wire each stage with `dup2`, close all unused descriptors, then wait.

**Rejected:** Running pipeline commands one at a time.

**Reason:** Pipeline stages must run concurrently. Sequential execution can deadlock or change behavior for producers and consumers.

---

### Decision 12 — Clean up pipe descriptors aggressively

**Chosen:** Children and parent close unused pipe ends.

**Rejected:** Relying on process exit to close everything eventually.

**Reason:** A leaked pipe write end can keep a reader blocked forever. Descriptor hygiene is a central shell lesson.

---

### Decision 13 — Use the last pipeline stage as the pipeline status

**Chosen:** Pipeline status is the exit status of the final command.

**Rejected:** Returning the first failure or an aggregate status.

**Reason:** This matches the common shell convention and keeps behavior predictable.

---

### Decision 14 — Support background jobs without full terminal job control

**Chosen:** Background simple commands and pipelines run in their own process group and are tracked in a `JobTable`.

**Rejected:** Implementing full `fg`, `bg`, `Ctrl-Z`, `tcsetpgrp`, and stopped-job control in V1.

**Reason:** Background jobs demonstrate non-blocking process management and reaping. Full terminal job control is a more advanced scope and was intentionally deferred.

---

### Decision 15 — Keep foreground jobs in the shell process group

**Chosen:** Foreground jobs remain in the shell’s process group while full terminal handoff is deferred.

**Rejected:** Moving foreground jobs to their own group without `tcsetpgrp`.

**Reason:** Moving foreground jobs to a separate process group without handing over the terminal can cause terminal-reading programs to receive `SIGTTIN` and stop. Keeping foreground jobs in the shell group avoids that incomplete state.

---

### Decision 16 — Temporarily ignore SIGINT in the parent while waiting

**Chosen:** Foreground children restore default SIGINT behavior; the parent shell ignores SIGINT while waiting.

**Rejected:** Letting Ctrl-C kill the shell.

**Reason:** Ctrl-C should interrupt the foreground job, not terminate the shell. At the prompt, Ctrl-C aborts the input line and sets status 130.

---

### Decision 17 — Make startup rc and history simple and explicit

**Chosen:** Read `~/.pyshellrc` unless `--no-rc` is supplied. Store interactive history in `~/.pyshell_history`.

**Rejected:** Full shell profile/login file compatibility.

**Reason:** The project needs enough startup/history behavior for a real shell feel without imitating all Bash/Zsh initialization rules.

---

## Consequences

**Positive:**
- The project demonstrates real shell mechanics.
- The architecture is testable by stage.
- Process execution does not hide behind `subprocess`.
- Builtin state mutation is honest.
- Redirection and pipelines use real file descriptor operations.
- Background job handling and reaping are visible.
- Signal behavior is documented and deliberate.
- Native Windows limitations are stated clearly.
- The CLI is small and reviewable.

**Negative / Trade-offs:**
- The shell is POSIX-targeted and not fully native-Windows compatible.
- It is not Bash compatible.
- Full terminal job control is deferred.
- There is no command substitution, glob expansion, here-docs, functions, loops, or advanced parameter expansion.
- Expanded values are not field-split.
- Some common shell edge cases are intentionally out of scope.
- Foreground jobs share the shell process group until terminal handoff is implemented.

---

## Alternatives Not Explored

- `subprocess.run()` engine.
- Shell grammar generated by parser generator.
- Full Bash grammar.
- Full POSIX shell compliance.
- Native Windows process engine.
- Terminal emulator UI.
- Remote shell service.
- Advanced job control with `fg`, `bg`, `Ctrl-Z`, and `tcsetpgrp`.
- Command substitution.
- Glob expansion.
- Here-docs.
- Shell functions and aliases.
- Audit logging.

---

*Constitution reference: Article 1 (Python fundamentals and architectural thinking), Article 3.3 (scope discipline), Article 4 (quality proportional to scope), Article 5 (trade-off documentation), Article 6 (verification), and Article 7 (progressive complexity).*

---


# Technical Design Document
## App — PyShell Lab
**Process Control Systems Group | Document 2 of 5**

---

## Overview

PyShell Lab is an educational POSIX-style shell written in Python. It provides an interactive REPL and script mode, parses shell-like command text into explicit AST dataclasses, performs quote-sensitive expansion, executes stateful builtins in the parent process, and executes external commands through POSIX process primitives.

**Package:** `pyshell_lab`  
**Console script:** `pyshell`  
**Python:** `>=3.11`  
**Runtime dependencies:** none  
**Primary target:** Linux/macOS/WSL  
**Native Windows:** lexer/parser/builtin coverage; POSIX execution skipped or unavailable  
**Execution engine:** `fork` / `execvpe` / `waitpid`

---

## System Context

```text
Terminal / Script File
  │
  ▼
Shell.run_interactive() / Shell.run_script()
  │
  ├── load ~/.pyshellrc unless --no-rc
  ├── load/save interactive history
  ├── install shell signal handlers
  ├── read command line
  └── execute_line()
        │
        ▼
      parse_line()
        │
        ├── lex()
        ├── Parser.parse()
        └── AST command object
        │
        ▼
      execute()
        │
        ├── expand words
        ├── collect prefix assignments
        ├── apply redirections
        ├── run parent builtin
        ├── fork external child
        ├── wire pipelines
        ├── manage background jobs
        └── decode wait status
```

---

## Main Package Areas

```text
src/pyshell_lab/
  __init__.py
  ast.py          # structured command objects
  lexer.py        # quote-aware tokenizer
  parser.py       # recursive-descent parser
  expansion.py    # variable and tilde expansion
  executor.py     # fork/exec/redirection/pipeline execution
  builtins.py     # cd, pwd, export, jobs, type, which, etc.
  jobs.py         # background job table and reaping
  signals.py      # Ctrl-C and child signal helpers
  state.py        # mutable shell state
  repl.py         # interactive and script loops
  history.py      # ~/.pyshell_history
  config.py       # ~/.pyshellrc
  main.py         # CLI entry point
```

---

## Command Processing Flow

```text
input line
  │
  ▼
lexer
  ├── WORD tokens
  ├── OP tokens
  ├── quote-preserving WordPart tuples
  ├── escaped character markers
  └── comments beginning at word-start "#"
  │
  ▼
parser
  ├── SimpleCommand
  ├── Pipeline
  ├── BackgroundCommand
  └── CommandSequence
  │
  ▼
expansion
  ├── tilde expansion at leading unquoted part
  ├── $VAR
  ├── ${VAR}
  ├── $?
  ├── $$
  └── single-quote suppression
  │
  ▼
executor
  ├── assignments
  ├── parent builtins
  ├── child builtins in pipelines/background
  ├── fork/exec external commands
  ├── redirection
  ├── pipeline fd wiring
  ├── background job table
  └── wait status
```

---

## Core Data Structures

### `WordPart`

```python
@dataclass(frozen=True)
class WordPart:
    text: str
    quote: Literal["none", "single", "double"] = "none"
```

Purpose:
- preserve quote context after lexing
- allow expansion to behave differently for single, double, and unquoted text
- preserve escaped-character markers until rendering/expansion

---

### `Token`

```python
@dataclass(frozen=True)
class Token:
    kind: Literal["WORD", "OP"]
    value: str
    position: int
    parts: tuple[WordPart, ...] = ()
```

Purpose:
- carry token kind and source position
- preserve word parts for later expansion
- represent shell operators separately from words

---

### `CommandWord`

```python
@dataclass(frozen=True)
class CommandWord:
    parts: tuple[WordPart, ...]
```

Purpose:
- typed shell word representation
- exposes `.text` for display/assignment detection
- passed from parser into expansion

---

### `Redirection`

```python
@dataclass(frozen=True)
class Redirection:
    operator: Literal[">", ">>", "<", "2>", ">&", "2>&"]
    target: CommandWord
```

Supported forms:
- `> file`
- `>> file`
- `< file`
- `2> file`
- `>&2`
- `2>&1`
- `2>&-`

---

### `SimpleCommand`

```python
@dataclass(frozen=True)
class SimpleCommand:
    words: tuple[CommandWord, ...]
    redirections: tuple[Redirection, ...] = ()
```

---

### `Pipeline`

```python
@dataclass(frozen=True)
class Pipeline:
    commands: tuple[SimpleCommand, ...]
```

---

### `BackgroundCommand`

```python
@dataclass(frozen=True)
class BackgroundCommand:
    command: CommandNode
```

---

### `CommandSequence`

```python
@dataclass(frozen=True)
class CommandSequence:
    items: tuple[SequenceItem, ...]
```

Connectors:
- `;`
- `&&`
- `||`

---

### `ShellState`

```python
@dataclass
class ShellState:
    cwd: str
    previous_cwd: str | None
    variables: dict[str, str]
    exported_env: dict[str, str]
    last_status: int
    jobs: JobTable
    history: list[str]
```

Purpose:
- current directory
- previous directory for `cd -`
- shell variables
- exported environment
- `$?`
- background jobs
- in-memory command history

---

## Lexer Design

Recognized operators:
```text
&& || 2>& >> >& 2> | > < & ;
```

Important lexer behavior:
- whitespace separates tokens
- comments begin with `#` only when `#` begins a word
- single quotes preserve literal text
- double quotes allow only selected backslash escapes
- outside quotes, backslash escapes one character
- quote context is preserved in `WordPart`
- unterminated quotes raise `LexerError`
- dangling escape raises `LexerError`

---

## Parser Design

The parser is recursive descent.

Parsing order:
```text
sequence → pipeline → simple command
```

Sequence rules:
- `;`, `&&`, and `||` connect commands
- empty commands are rejected
- `&` backgrounds only the immediately preceding pipeline/simple command
- `&&` or `||` immediately after background command is rejected

Pipeline rules:
- `|` connects simple commands
- missing command before/after pipe raises `ParserError`
- assignment-only pipeline stage is rejected later by executor

Simple command rules:
- words and redirections may appear together
- redirection requires a following word target
- redirection without command is rejected

---

## Expansion Design

Supported:
- `~`
- `~/path`
- `$VAR`
- `${VAR}`
- `$?`
- `$$`

Rules:
- single quotes suppress expansion
- double quotes allow expansion
- unquoted text allows expansion
- tilde expansion happens only on the first unquoted word part
- lookup order is same-line assignment overlay, shell variables, exported environment
- no field splitting
- no glob expansion
- no parameter modifiers
- unclosed `${...` raises `ExpansionError`

---

## Assignment Semantics

Leading `NAME=value` words are collected as assignments.

Cases:
- `NAME=value` with no command mutates shell variables
- `NAME=value command` applies only to that command environment
- `A=1 B=$A cmd` lets later same-line assignment values see earlier assignment values
- assignment name must be unquoted
- `FOO=bar echo $FOO` does not make `FOO` visible to the same command’s argument expansion unless it already existed

---

## Builtin Design

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

Parent-process builtins:
- run in the shell process when foreground
- can mutate shell state
- use fd save/restore for redirection
- temporary prefix assignments are restored after execution

Child-process builtins:
- used in pipelines or background jobs
- do not mutate parent shell state
- exit using `os._exit(status)` after flushing stdout/stderr

---

## External Execution

Foreground external command flow:
```text
collect assignments
expand argv
validate redirections
fork
  child:
    restore default child signals
    apply redirections
    execvpe(argv[0], argv, env)
  parent:
    ignore SIGINT while waiting
    waitpid(child)
    decode status
    restore SIGINT handler
```

Exec failure mapping:
- command not found → `127`
- permission denied → `126`
- other exec `OSError` → `126`

---

## Redirection Design

File redirection:
- `>` opens stdout truncate
- `>>` opens stdout append
- `<` opens stdin read-only
- `2>` opens stderr truncate

Duplication:
- `2>&1` makes stderr a copy of stdout
- `>&2` makes stdout a copy of stderr
- `2>&-` closes stderr

Parent builtin redirection:
1. save target fd with `os.dup()`
2. apply each redirection with `os.open()`/`os.dup2()`
3. run builtin
4. flush stdout/stderr
5. restore original fd with `os.dup2()`
6. close saved fd

If a later redirection fails, earlier saved redirections are rolled back.

---

## Pipeline Design

Pipeline flow:
```text
create N-1 pipes
for each stage:
  fork
  child:
    restore signals
    set background pgid if needed
    dup previous pipe read end to stdin
    dup next pipe write end to stdout
    close all pipe fds
    apply redirections
    run builtin or exec
parent:
  close all pipe fds
  foreground: wait for all pids
  background: add job and return
```

Important:
- all pipeline stages are forked before waiting
- parent closes all pipe fds
- each child closes all pipe fds after duplication
- status is final stage exit status
- background pipelines get a process group

---

## Background Job Design

`JobTable` stores:
- job id
- command line
- status
- pids
- pgid
- timestamps
- exit status
- per-pid statuses

Reaping:
- uses `waitpid(-1, WNOHANG)`
- records each pid status
- reports a multi-stage pipeline only once all pids finish
- final job status is based on last pipeline stage
- `jobs` prints completed jobs once and removes them

---

## Signal Design

Installed in shell:
- SIGINT handler raises `KeyboardInterrupt` at prompt
- SIGTSTP/SIGTTIN/SIGTTOU are ignored while job control is deferred

Child setup:
- child restores default SIGINT and SIGQUIT before exec
- stop signals remain ignored because full job control is deferred

Foreground wait:
- parent ignores SIGINT while waiting
- restores previous handler afterward

Status:
- signal-terminated child returns `128 + signal`

---

## REPL and Script Mode

Interactive mode:
- installs signal handlers
- loads history
- loads rc file unless disabled
- shows prompt with last status and cwd
- reports finished jobs before each prompt
- saves history on exit

Script mode:
- installs signal handlers
- loads rc file unless disabled
- reads script lines
- skips blank lines and full-line comments
- does not read/write interactive history
- returns last status or explicit exit status

---

## Config and History

Startup rc:
```text
~/.pyshellrc
```

History:
```text
~/.pyshell_history
```

History limit:
```text
1000 entries
```

`--no-rc` disables rc loading in both interactive and script mode.

---

## Known Limits

- Not Bash-compatible.
- No shell functions.
- No loops except `;`, `&&`, and `||` sequencing.
- No field splitting.
- No glob expansion.
- No command substitution.
- No here-docs.
- No positional parameters.
- No full job control.
- No native Windows execution engine.
- No audit log.
- No execution-plan debug output in current scope.

---

## Verification Summary

The repository configures:
- Python 3.11+
- zero runtime dependencies
- pytest
- Ruff
- mypy
- coverage over `pyshell_lab`
- CI across Ubuntu, macOS, and Windows
- coverage fail-under 85 on Linux and macOS
- lint/type-check job on Ubuntu
- native Windows matrix for non-POSIX surfaces

---

*Constitution reference: Article 4 (engineering quality), Article 6 (behavior verification), Article 7 (progressive complexity), and Article 8 (valid learner work).*

---


# Interface Design Specification
## App — PyShell Lab
**Process Control Systems Group | Document 3 of 5**

---

## Public CLI Interface

### Console command

```bash
pyshell [--no-rc] [--version] [script]
```

### Interactive mode

```bash
pyshell
```

Behavior:
- loads `~/.pyshellrc` unless `--no-rc`
- loads `~/.pyshell_history`
- starts prompt:
```text
pyshell[<last_status>] <cwd>$ 
```

### Script mode

```bash
pyshell script.psh
pyshell --no-rc examples/demo.psh
```

Behavior:
- loads `~/.pyshellrc` unless `--no-rc`
- executes nonblank, non-comment lines
- returns final status
- does not persist interactive history

### Version

```bash
pyshell --version
```

---

## CLI Options

| Option | Description |
|---|---|
| `script` | Optional `.psh` script to run |
| `--no-rc` | Do not read `~/.pyshellrc` |
| `--version` | Print installed version |

---

## Command Language

### Simple command

```bash
echo hello
pwd
cd /tmp
```

### Sequence

```bash
cmd1; cmd2
cmd1 && cmd2
cmd1 || cmd2
```

### Pipeline

```bash
echo hello | wc -c
ls /nope 2>&1 | wc -l
```

### Background command

```bash
sleep 10 &
echo a; echo b &
```

`&` applies only to the immediately preceding simple command or pipeline.

### Redirection

```bash
command > file
command >> file
command < file
command 2> file
command 2>&1
command >&2
command 2>&-
```

### Assignment

```bash
NAME=value
NAME=$OTHER-suffix
export NAME=value
NAME=value command
```

---

## Builtins

| Builtin | Purpose |
|---|---|
| `cd` | Change shell current directory |
| `pwd` | Print current directory |
| `exit` | Exit the shell |
| `help` | List builtins |
| `echo` | Print arguments |
| `export` | Set/export variables for child processes |
| `unset` | Remove variable/env entry |
| `env` | Print exported environment |
| `set` | Print or set shell variables |
| `history` | Print interactive command history |
| `jobs` | Print/reap background jobs |
| `type` | Explain builtin or path lookup |
| `which` | Print external command path |

---

## Expansion Contract

Supported expansions:
```bash
$VAR
${VAR}
$?
$$
~
~/path
```

Rules:
- single quotes suppress variable expansion
- double quotes allow variable expansion
- unquoted words allow variable expansion
- leading unquoted tilde expands to home
- no field splitting
- no globbing
- unset variables expand to empty string
- invalid/unclosed `${...` raises expansion error

---

## Variable Contract

Shell variables:
```bash
NAME=value
set NAME=value
```

Exported variables:
```bash
export NAME=value
export NAME
```

Unexport:
```bash
unset NAME
```

Child command environment:
```bash
NAME=value command
```

Assignment-only command:
```bash
NAME=value
```
sets shell variable and returns `0`.

---

## Exit Status Contract

| Situation | Status |
|---|---:|
| Success | `0` |
| External command failure / redirect I/O / fork / pipe failure | `1` |
| Lexer/parser/expansion error or builtin usage error | `2` |
| Command not found | `127` |
| Permission denied | `126` |
| Ctrl-C at prompt | `130` |
| Signal-terminated child | `128 + signal` |

`$?` exposes the last status.

---

## Error Output Contract

Errors are written to stderr with a `pyshell:` prefix where appropriate.

Examples:
```text
pyshell: unclosed single quote at position 5
pyshell: redirection failed: ...
pyshell: external command execution requires POSIX/Linux/macOS/WSL
```

---

## History Interface

Interactive history:
```text
~/.pyshell_history
```

Behavior:
- loaded at interactive startup
- saved at interactive exit
- capped at 1000 entries
- uses stdlib `readline` when available
- script mode does not read/write history

---

## Startup Config Interface

Startup file:
```text
~/.pyshellrc
```

Behavior:
- read in interactive and script mode unless `--no-rc`
- blank and full-line comment lines skipped
- each line is executed in current shell state
- `exit` inside rc exits startup with that status

---

## Public Python API Surface

Although the project is CLI-first, the modules are structured for testing and reuse.

Common imports:
```python
from pyshell_lab.parser import parse_line
from pyshell_lab.lexer import lex
from pyshell_lab.expansion import expand_word, expand_words
from pyshell_lab.executor import execute
from pyshell_lab.state import ShellState
from pyshell_lab.repl import Shell
```

Primary functions/classes:
- `lex(line)`
- `parse_line(line)`
- `expand_word(word, state)`
- `expand_words(words, state)`
- `execute(node, state, command_line="")`
- `Shell.run_interactive(load_rc=True)`
- `Shell.run_script(path, load_rc=True)`
- `ShellState`

---

## Side Effects

| Operation | Side Effect |
|---|---|
| `cd` | Changes process working directory |
| `export`, `unset`, `set` | Mutates shell variable/environment state |
| external command | Forks child process and may execute arbitrary program by path search |
| redirection | Opens/creates/truncates files as requested |
| pipeline | Opens pipes, forks every stage |
| background command | Returns before child completes and stores job metadata |
| `jobs` | Reaps finished child processes |
| interactive history | Reads/writes `~/.pyshell_history` |
| rc loading | Reads and executes `~/.pyshellrc` |
| script mode | Reads script file |
| Ctrl-C | Interrupts prompt or foreground job |

---

## Unsupported Interface

Not supported:
- Bash compatibility
- command substitution
- globbing
- here-docs
- shell functions
- aliases
- arrays
- positional parameters
- subshell syntax
- full `fg` / `bg` job control
- native Windows fork/exec execution

---

*Constitution reference: Article 4 (input/output boundaries), Article 6 (verification), and Article 8 (understandable and verifiable work).*

---


# Runbook
## App — PyShell Lab
**Process Control Systems Group | Document 4 of 5**

---

## Requirements

### Runtime

- Python 3.11+
- POSIX platform for full execution:
  - Linux
  - macOS
  - Windows through WSL

### Native Windows

Native Windows can exercise lexer/parser/builtin areas, but full external command execution requires POSIX primitives.

### Runtime dependencies

None.

### Development dependencies

- pytest
- pytest-cov
- Ruff
- mypy

---

## Installation

### Editable development install

```bash
python -m pip install -e ".[dev]"
```

### Pinned dev tooling

```bash
python -m pip install -e . -r requirements-dev.txt
```

---

## First Smoke Test

```bash
pyshell --no-rc
```

Inside the shell:

```bash
echo hello
NAME=Ada
echo "hi $NAME"
pwd
exit
```

Expected:
- prompt appears
- command output prints
- variables expand
- exit returns to terminal

---

## Script Smoke Test

Create `demo.psh`:

```bash
echo hello
NAME=Ada
echo "hi $NAME"
false && echo skipped || echo recovered
```

Run:

```bash
pyshell --no-rc demo.psh
```

Expected:
```text
hello
hi Ada
recovered
```

---

## Core Feature Demos

### Pipeline

```bash
echo hello | wc -c
```

Expected:
```text
6
```

### Redirection

```bash
echo hello > out.txt
cat < out.txt
```

### Stderr duplication

```bash
ls /nope 2>&1 | wc -l
```

### Background job

```bash
sleep 5 &
jobs
```

### Exported env

```bash
export NAME=Ada
env | grep NAME
```

### Temporary env

```bash
NAME=Ada env | grep NAME
```

---

## Startup File

Create:

```bash
echo 'export GREETING=hello' > ~/.pyshellrc
```

Run:

```bash
pyshell
echo $GREETING
```

Skip rc:

```bash
pyshell --no-rc
```

---

## History

Interactive history file:

```text
~/.pyshell_history
```

Notes:
- script mode does not read/write history
- history caps at 1000 entries
- readline integration is automatic when stdlib `readline` is available

---

## Testing

### Full local test run

```bash
python -m pytest
```

### With coverage

```bash
python -m pytest --cov=pyshell_lab --cov-report=term-missing
```

### Lint

```bash
ruff check .
ruff format --check .
```

### Type check

```bash
mypy
```

---

## CI Parity

The CI matrix runs:
- Ubuntu latest
- macOS latest
- Windows latest
- Python 3.11, 3.12, and 3.13

Coverage:
- Linux/macOS run coverage with an 85% fail-under gate
- Windows runs test coverage without the POSIX fail-under gate because execution tests are skipped

Lint/type-check:
- Ubuntu
- Python 3.12
- pinned dev toolchain
- Ruff check
- Ruff format check
- mypy

---

## Health Checks

### Parser/lexer health

```bash
python - <<'PY'
from pyshell_lab.parser import parse_line
print(parse_line('echo "hello $USER" | wc -c'))
PY
```

### POSIX execution health

```bash
printf 'echo hello\n' > /tmp/pyshell-smoke.psh
pyshell --no-rc /tmp/pyshell-smoke.psh
```

### Redirection rollback check

```bash
pyshell --no-rc
echo before
pwd > /tmp/pyshell-pwd.txt
echo after
exit
```

Expected:
- `after` still prints to terminal
- stdout was restored after builtin redirection

---

## Troubleshooting

### `external command execution requires POSIX/Linux/macOS/WSL`

Cause:
- running on native Windows or a host without `os.fork`

Fix:
- run under WSL, Linux, or macOS for full process execution
- continue using native Windows for lexer/parser/builtin tests when applicable

---

### Command not found

Expected status:
```text
127
```

Check:
- command spelling
- exported `PATH`
- use `export PATH=...` to affect external lookup
- shell variables that are not exported do not affect external lookup

---

### Permission denied

Expected status:
```text
126
```

Check:
- file exists
- executable bit set
- path is not a directory
- permission allows execution

---

### Redirection failed

Expected status:
```text
1
```

Common causes:
- target directory missing
- permission denied
- empty redirection target
- invalid descriptor in `>&` form

---

### Parser error after `|`

Cause:
```bash
echo hi |
```

Fix:
```bash
echo hi | wc -c
```

---

### `Ctrl-Z` does nothing

Expected:
- full terminal job control is intentionally deferred
- stop signals are ignored to prevent the shell from being left blocked on stopped children

---

### Background job not visible forever

Expected:
- `jobs` prints completed jobs once and then removes them
- the prompt loop also reports finished jobs before reading a new line

---

### `$VAR` did not split into multiple arguments

Expected:
- field splitting is intentionally not implemented
- an expanded value remains one argument

---

## Maintenance Notes

- Preserve the lexer/parser/expansion/executor separation.
- Do not replace the execution core with `subprocess.run`.
- Keep parent builtins in the parent when foreground.
- Add tests before changing redirection ordering.
- Add tests before changing pipe fd cleanup.
- Add tests before changing signal behavior.
- Keep full job control deferred unless implementing `tcsetpgrp`, `fg`, `bg`, and stopped-job recovery together.
- Keep native Windows limitations explicit.
- Keep runtime dependencies at zero unless there is a clear ADR-level reason.
- Keep CI across Linux, macOS, and Windows.

---

*Constitution reference: Article 6 (behavior verification), Article 5 (constraints and trade-offs), and Article 8 (verifiable learner work).*

---


# Lessons Learned
## App — PyShell Lab
**Process Control Systems Group | Document 5 of 5**

---

## Why This Design Was Chosen

This design was chosen because a shell is one of the clearest ways to demonstrate the boundary between text parsing and operating-system process control. The project had to show the full path: user input, tokens, AST objects, expansion, process creation, file descriptor manipulation, waiting, status decoding, and stateful builtins.

The project deliberately avoids pretending to be Bash. Bash compatibility is huge. A portfolio shell is stronger when its scope is clear: implement a focused POSIX-style subset well, document the omissions honestly, and show the low-level primitives directly.

The decision not to use `subprocess.run` is central. The point is not to launch commands in the easiest way; it is to show why shells need fork, exec, pipes, dup2, waitpid, process groups, and signal handling.

---

## What Was Intentionally Omitted

**Full Bash compatibility:** Out of scope.

**Command substitution:** Deferred.

**Globbing:** Deferred.

**Field splitting:** Deferred; expanded values remain one argument.

**Here-docs:** Deferred.

**Shell functions and aliases:** Deferred.

**Loops and conditionals beyond `;`, `&&`, and `||`:** Deferred.

**Full terminal job control:** Deferred because `fg`, `bg`, `Ctrl-Z`, process groups, and `tcsetpgrp` should be implemented together.

**Native Windows process execution:** Out of scope because POSIX primitives are required.

**Audit log and execution-plan debug:** Documented as deferred.

---

## Biggest Weakness

The biggest weakness is incomplete job control. Background jobs work, and foreground Ctrl-C behavior is deliberate, but the shell does not yet support `fg`, `bg`, `Ctrl-Z`, or full terminal process-group handoff. This is the right scope decision for V1, but it should be clearly stated during portfolio review.

The second weakness is expansion behavior. No field splitting and no globbing make the shell simpler and safer to reason about, but they differ from user expectations formed by Bash.

The third weakness is POSIX-only execution. This is honest and technically correct, but it means full demos should run on Linux, macOS, or WSL.

---

## Scaling Considerations

**If compatibility grows:**
- add field splitting with quote-aware boundaries
- add glob expansion
- add command substitution
- add here-docs
- add positional parameters
- add more POSIX shell grammar coverage

**If job control grows:**
- introduce foreground process groups
- use `tcsetpgrp` to hand terminal control to foreground jobs
- implement stopped job states
- add `fg` and `bg`
- handle `SIGCHLD` or deliberate polling carefully

**If diagnostics grow:**
- add execution-plan debug output
- show redirection and pipe layout before execution
- expose AST pretty-printing

**If safety grows:**
- add optional audit log
- record command start/finish/status
- track background job lifecycle more durably

---

## What the Next Refactor Would Be

1. **Execution plan object** — convert parsed/expanded commands into an inspectable plan before forking.

2. **Field splitting and globbing** — add quote-aware post-expansion argument processing.

3. **Full job control** — implement process-group handoff, `fg`, `bg`, and stopped job management.

4. **Better script diagnostics** — include line numbers and failing command text.

5. **Audit/debug mode** — optional structured log of commands, forks, redirections, and statuses.

---

## What This Project Taught

- **A shell is a compiler plus process manager.** It parses text into structured commands, then maps them to OS operations.

- **Quote context must survive lexing.** Expansion cannot be correct if the lexer destroys single/double/unquoted information.

- **Parent builtins are necessary.** A child cannot change the parent shell’s current directory or persistent environment.

- **Pipes require descriptor discipline.** Forgetting to close one pipe end can hang the whole pipeline.

- **Redirection order matters.** `2>&1` depends on where stdout points at that moment.

- **Signals are architecture, not decoration.** Ctrl-C behavior depends on process groups and parent/child signal disposition.

- **Exactly matching Bash is not the goal.** The goal is to build a defensible educational shell and state its limits honestly.

- **POSIX primitives are worth learning directly.** `fork`, `execvpe`, `dup2`, `pipe`, and `waitpid` explain what higher-level APIs hide.

---

*Constitution v2.0 checklist: This document satisfies Article 5 (trade-off documentation), Article 6 (verification), and Article 7 (progressive complexity) for PyShell Lab.*
