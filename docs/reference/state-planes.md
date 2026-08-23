# State — session / client / db

> **Diátaxis:** reference · **Canonical:** `docs/reference/state-planes.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 6. State — three kinds (do not merge them in your head)

`from ux_channel import state` → `st = state(ch, …)`

| Kind | Lives | Use for | Not for |
|------|-------|---------|---------|
| **session** | Server draft / session store | Cart counts, wizard steps | Money ledgers |
| **client** | Browser-visible (allow-listed paths) | Theme, UI chrome | `amount`, roles, secrets |
| **db** | **Your** database | Durable business records | Pretending channel stores orders |

**Quantity / money:** load via foundations (`Quantity.from_store…`); never trust client paths for magnitudes.  
**RMW:** use store semantics / drafts carefully under concurrency (see host stores docs).

Power backends: `from ux_channel.host.stores import MemoryStateStore` (not on root).

---
