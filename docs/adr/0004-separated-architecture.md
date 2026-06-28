# ADR 0004: Separate Lexer, Parser, Expansion, And Executor

## Status

Accepted

## Context

A shell that splits strings and immediately forks is hard to test and hard to reason about.

## Decision

PyShell Lab uses separate modules for lexing, parsing, expansion, and execution. The parser emits structured dataclasses before execution begins.

## Consequences

Parser tests can run without launching processes, and execution code receives a clear command model instead of raw strings.
