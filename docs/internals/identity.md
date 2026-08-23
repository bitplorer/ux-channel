# What ux-channel is (and is not)

> **Diátaxis:** explanation · **Canonical:** `docs/internals/identity.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 1. What this library is (and is not)

### One sentence

**ux-channel** is a **server-driven UI protocol and host**: the browser sends a signed **Intent** `{ action, args, cap }`; the server runs an **action**, optionally re-renders **regions**, and returns a **Result** `{ ok, ops[], error? }` that the client applies to the DOM (morph, toast, navigate, …).

```text
  Human clicks button
        │
        ▼
  Intent { action, args, cap }     ◄── cap proves “this principal may do this action with these args”
        │
        ▼
  Host: verify cap → run handler → update state/regions
        │
        ▼
  Result { ok, ops[] }             ◄── ordered effects, not free-form HTML soup
        │
        ▼
  Client applies ops (morph #region, toast, push_url, …)
```

### What it *is*

| It is | Meaning |
|-------|---------|
| A **protocol** | Intent / Result / ops / error shape shared by peers (Python host, Rust peer, future clients) |
| A **trust model** | **Capabilities** (caps) bind action + args + optional principal; not “session cookie alone = all actions” |
| A **host runtime** | `Channel`, regions, action registry, hooks, state façade |
| A **wire option** | JSON always works; **CXB** is a compact binary upgrade for the same IR |
| Multi-caller | Humans (UI), agents (`agents(ch)`), MCP, islands — **same registry**, different doors |

### What it is *not*

| It is not | Do not assume |
|-----------|----------------|
| A full frontend framework | You still choose HTML / React / ux-dom / Jinja for markup |
| An ORM or database | `state().db` is **guards**, not storage you get for free |
| “Just REST CRUD” | The unit of work is **action + signed args**, not resource URLs alone |
| Client-authoritative business logic | The browser must not invent prices, balances, or durable truth |
| Multiplayer game netcode | Realtime/WebRTC is an **optional plane**, not the core loop |
| A second language runtime for Python apps | Rust is a **second implementation** of the same law, not required to ship a Python app |

### Two artifacts in the monorepo

| Artifact | Path | You need it if… |
|----------|------|------------------|
| **Python host** | `python/` | Building a real app (almost everyone) |
| **Rust crate** | `rust/` | Host+peer kernel/runtime, classic gate, `uxc_check`, interop |

**Law** (both must obey): `SPEC/` + `conformance/` golden vectors.  
If Python and Rust disagree, **vectors win**.

Architecture (EffectGraph, proofs, flow correlation, peer kernel) is documented in
[`SPEC/architecture/`](../../SPEC/architecture/README.md). Classic IR 0.1 clients stay on the floor.

---
