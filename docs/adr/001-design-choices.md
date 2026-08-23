# ADR 001 — Intent → Result, caps over args

> **Diátaxis:** ADR · **Canonical:** `docs/adr/001-design-choices.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

**Status:** accepted (current law)  
**Date:** 2026-08-24 (extracted from START_HERE §8; decisions predate this extract)

## Context

The host must speak the same IR to browsers, agents, and a Rust peer without
becoming a frontend framework or an ORM.

## Decision

## 8. Design choices (why it is this way)

| Choice | Why |
|--------|-----|
| **Intent → Result**, not “RPC returns HTML only” | Same IR for DOM, agents, hardware, second languages |
| **Caps over args**, not only session cookies | UI cannot escalate args; agents need the same seal |
| **Sorted compact JSON args_hash** | Cross-language parity (Python ↔ Rust) without ambiguous key order |
| **Ops list** | Ordered, inspectable effects; easy to log, test, and morph |
| **Regions** | Partial update without inventing a client store of truth |
| **Root = application surface only** | Power APIs stay in packages (`host.stores`, `agent_runtime`, …) so the library does not look like 200 peer concepts |
| **Hooks (before/after)** | Cross-cutting policy without forking Channel |
| **Optional planes** | Realtime/MCP/bridge do not load on `import ux_channel` |
| **Conformance vectors** | “Works on my machine” is not law; goldens are |
| **JSON floor + CXB upgrade** | Always interoperable; optimize when needed |

Permanence strata and anti-bloat doors: [LONGEVITY.md](../../LONGEVITY.md).

---

## Consequences

- Caps seal action + args; UI cannot escalate unsigned fields.
- Root `__all__` stays an application surface; power APIs stay in packages.
- Permanence strata: [../../LONGEVITY.md](../../LONGEVITY.md).
- Monorepo decision: [../../ARCHITECTURE.md](../../ARCHITECTURE.md).
