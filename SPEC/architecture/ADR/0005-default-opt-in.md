# ADR 0005 — Default opt-ins via negotiation

## Decision
When both sides support a safe feature, enable it automatically (`effects/proofs/flow: auto`). Explicit only for sharp edges (outbox, strict unknown, maximal emit).

## Consequences
Fewer manual flags; classic fallback when peer lacks support.
