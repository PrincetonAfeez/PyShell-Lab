# ADR 0007: Apply Redirection With Descriptor Save And Restore

## Status

Accepted

## Context

Redirection must affect a command without permanently changing the shell's own standard streams.

## Decision

Child commands apply redirection directly before `exec`. Parent-process builtins save the target descriptor, apply the redirect, run the builtin, flush output, and restore the original descriptor.

## Consequences

`echo hello > out.txt` works, and the shell prompt still prints to the terminal afterward.
