# ADR 0003 — Peer kernel has no DOM

## Decision
Peer kernel is generic apply/session/budgets/proof only. Browser behavior lives in `web.v1` drivers.

## Consequences
Agents and wire peers share the same kernel package.
