# ADR 0011: Defer Bytecode-Style Execution Plans

## Status

Accepted

## Context

Execution plans are useful for teaching, but they are optional stretch work after the core shell is stable.

## Decision

The first implementation executes directly from the parsed command dataclasses.

## Consequences

The architecture remains simple. A later version can lower the same AST into explicit plan instructions.
