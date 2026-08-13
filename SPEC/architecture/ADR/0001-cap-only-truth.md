# ADR 0001 — Cap is the only truth edge

## Context
Need a single place auditors trust for “may this action run with these args?”

## Decision
Intent + Cap only. Result, flow_id, and proof never authorize handlers.

## Consequences
All money/delete paths go through Cap. Multi-step flows mint per-step Caps.

## Alternatives rejected
Nested Result authority; session cookie as action permission.
