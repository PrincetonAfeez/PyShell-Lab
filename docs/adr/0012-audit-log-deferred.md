# ADR 0012: Defer HMAC Audit Logging

## Status

Accepted

## Context

Tamper-evident audit logging is a good stretch feature, but it should not distract from correct parser and process behavior.

## Decision

HMAC audit logging is deferred until the core shell is stable.

## Consequences

No custom cryptography is introduced. A future implementation should use `hmac`, `hashlib`, and a chained previous-entry digest.
