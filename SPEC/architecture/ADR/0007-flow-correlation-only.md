# ADR 0007 — Trace is correlation only

## Decision
CEK **trace** groups related Intents. It is default-opt-in tagging for
multi-step host work. Peers ignore unknown meta. No peer Flow engine.
`meta.flow_id` is the wire-immortal alias of `meta.trace` (no wire break).

## Consequences
Backward compatible; resume is host-side. Encode: `flow_id` → `trace`
(never authority).
