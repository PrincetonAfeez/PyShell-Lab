# ADR 0006: Represent And Execute Pipelines Structurally

## Status

Accepted

## Context

Pipelines need multiple commands connected by file descriptors, not string concatenation.

## Decision

The parser emits a `Pipeline` containing `SimpleCommand` objects. The executor creates all pipes, forks all stages, wires descriptors with `dup2`, closes unused descriptors, and then waits.

## Consequences

Pipeline stages run concurrently. The pipeline status is documented as the status of the last command.
