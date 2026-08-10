# Naming constitution — intent ↔ name (idempotent speech)

**Law:** one *intent* maps to one *preferred name*.  
Where a second name exists (history, Rust parity, package shadowing), it is an **documented alias**, not a second concept.

Full product naming for Quantity/AX/etc.: [`python/docs/start/NAMING.md`](python/docs/start/NAMING.md).

---

## 1. How to read any name

Ask: **what job does this do?** Then match the table. If two spellings exist, the **Preferred** column is what you say and teach.

| Intent (what you want) | Preferred name | Also valid (same thing) | Never means |
|------------------------|----------------|-------------------------|-------------|
| One morphable DOM slot | **`Region`** | `@ch.region` function | RegionBook, Bridge |
| Registry of all slots on a Channel | **region registry** / **`RegionRegistry`** | `RegionBook`, `ch.regions` | a single Region |
| Discover region classes on disk | **`RegionDirectory`** | — | RegionBook itself |
| Create a capability token | **`mint`** | Python `sign` (alias; identical) | verify |
| Check a capability token | **`verify`** | — | mint |
| App-facing channel object | **`Channel`** | — | RegionBook |
| Client instruction in a Result | **`op`** / builders `morph`, `toast` | — | action |
| Named server handler | **`action`** | — | op, region |
| IR request document | **`Intent`** | — | Result |
| IR response document | **`Result`** | — | Intent |
| Wire codecs JSON/CXB | **`wire`** package | — | capability |
| Day-1 app imports | **`ux_channel.day1`** | root `ux_channel` exports | power packages |
| Cohesive code home | **`host` / `protocol` / …** packages | `zones.*` (navigation only) | “zone = implementation” |
| npm / JS island | **`Bridge`** | `bridges/*` | Region |
| Session/client/db guards API | **`state(ch)`** | `state_api` module | database driver |
| Agent tools façade | **`agents(ch)`** | `agents_api` | dual agent APIs |

---

## 2. Dual names that are **intentionally** the same function

### mint ≡ sign (capability create)

| | |
|--|--|
| **Intent** | Issue a capability token for an action + sealed args |
| **Preferred speech** | **mint** (matches Rust `CapService::mint`, product docs) |
| **Python historical** | `CapabilityService.sign` (itsdangerous heritage) |
| **Rule** | `mint(...)` and `sign(...)` are **one implementation**. Prefer **mint** in new code. |

```python
cap = svc.mint("Cart.add", {"sku": "a", "qty": 1})  # preferred
cap = svc.sign("Cart.add", {"sku": "a", "qty": 1})  # identical
```

### RegionRegistry ≡ RegionBook (slot registry)

| | |
|--|--|
| **Intent** | Hold every region uid → render on a Channel |
| **Preferred speech** | **region registry** |
| **Type names** | `RegionRegistry` (clear) = `RegionBook` (historical) |
| **Attribute** | `ch.regions` |
| **Rule** | Same class object. **Not** a rename of `Region`. |

```python
assert RegionRegistry is RegionBook
# everyday apps: use Region; the book is ch.regions
```

### day1 ≡ subset of root exports

| | |
|--|--|
| **Intent** | Import only the frozen app surface |
| **Preferred** | `from ux_channel.day1 import Channel, Region, …` |
| **Also fine** | `from ux_channel import Channel, Region` (same objects) |

---

## 3. Package names vs module names (no shadowing)

Some packages avoid colliding with a module file name:

| Package folder | Why that name | Module you import for the core idea |
|----------------|---------------|-------------------------------------|
| `security_plane/` | cannot be named `security/` (would shadow `security.py`) | `security_plane.security` or shim `ux_channel.security` |
| `paint/` | cannot be named `render/` (would shadow `render.py`) | morph/html live under `paint/` |
| `realtime/` | cannot be named `media/` (would shadow `media.py`) | webrtc/sfu modules |

**Speech:** say “security package”, “paint package”; imports may use plane suffix for physics of Python packaging.

Legacy shims keep `from ux_channel.security import safe_href` working.

---

## 4. Layers of speech (product → wire)

```text
Product speech     Region, mint cap, action, refresh
Type / API names   Region, RegionRegistry, CapabilityService.mint
Wire keys          op, ok, error, data-channel-id   (immortal — never “rename for taste”)
Package paths      host.regions, protocol.capability
```

Wire keys are **not** renamed to match prose. Prose maps *to* wire keys in TERMINOLOGY / SPEC.

---

## 5. Naming laws (stable)

1. **One intent → one preferred name** (table in §1).
2. **Aliases only for history or cross-language parity** — must be same object/function, documented here.
3. **Do not invent a third synonym** (no `SlotBook`, `CapForge`, etc. without a major version).
4. **Wire keys immortal** (`ops`, `ok`, `error`, `data-channel-*`).
5. **Region** always means one slot; registry always means the book/`ch.regions`.
6. **Bridge** never called region; **action** never called op.
7. **AX** = `agents(ch)` only; **state** day-1 = `state(ch)` only.

---

## 6. Quick self-check

| If you say… | You should write… |
|-------------|-------------------|
| “this badge region” | `class Badge(Region)` or `@ch.region` |
| “refresh all registered slots” | `ch.regions` / RegionRegistry |
| “issue a cap” | `svc.mint(...)` |
| “check the cap” | `svc.verify(...)` |
| “chart.js island” | Bridge, not Region |
| “what the client applies” | ops (`morph`, `toast`) |

---

## 7. Related docs

| Doc | Role |
|-----|------|
| [TERMINOLOGY.md](TERMINOLOGY.md) | Full glossary |
| [python/ONTOLOGY.md](python/ONTOLOGY.md) | Host concepts |
| [python/LAYOUT.md](python/LAYOUT.md) | Packages + shims |
| [python/docs/start/NAMING.md](python/docs/start/NAMING.md) | Quantity, AX, workplace laws |
