# ADR 0005: Run Stateful Builtins In The Shell Process

## Status

Accepted

## Context

Commands such as `cd`, `export`, and `unset` must affect the shell state used by later commands.

## Decision

Foreground stateful builtins run in the parent shell process. Builtins inside pipelines or background jobs run in children.

## Consequences

`cd` changes the shell's current directory. Pipeline stages remain isolated and do not mutate the parent shell.
