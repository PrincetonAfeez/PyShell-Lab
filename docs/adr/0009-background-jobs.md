# ADR 0009: Track And Reap Background Jobs

## Status

Accepted

## Context

Background jobs should return control to the prompt without leaving zombie processes.

## Decision

The shell stores background job metadata in a `JobTable` and periodically reaps finished children with `waitpid(..., WNOHANG)`.

## Consequences

`jobs` can report running and completed jobs, and normal background flow avoids zombies.
