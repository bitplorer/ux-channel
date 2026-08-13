# ADR 0006 — once/jti fail closed

## Decision
Atomic consume before side effects; if nonce store unavailable, reject once Caps.

## Consequences
Destructive actions depend on store availability; preferred over double execution.
