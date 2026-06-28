# ADR 0002: Target POSIX Platforms

## Status

Accepted

## Context

The project depends on `fork`, `exec`, `waitpid`, `pipe`, `dup2`, process groups, and Unix signal behavior. Native Windows does not provide the same APIs or semantics.

## Decision

The full shell targets Linux, macOS, and Windows through WSL. Native Windows can run non-process-control tests only.

## Consequences

The executor raises a clear platform error when external execution is attempted without POSIX support.
