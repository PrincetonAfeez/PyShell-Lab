# ADR 0001: Keep The Project CLI-Only

## Status

Accepted

## Context

The capstone is about shell architecture and the operating-system boundary. A web UI would add routing, rendering, and application-state concerns that do not help explain lexing, parsing, process creation, descriptors, or signals.

## Decision

PyShell Lab is a CLI-only application.

## Consequences

All effort stays focused on the shell loop, parser, executor, jobs, and documentation of POSIX behavior.
