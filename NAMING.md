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
| Registry of all slots on a Channel | **region registry** / **`RegionBook`** | `RegionBook`, `ch.regions` | a single Region |
| Discover region classes on disk | **`RegionDirectory`** | — | RegionBook itself |
| Create a capability token | **`mint`** | — (use mint only; Rust-parity) | verify |
| Check a capability token | **`verify`** | — | mint |
| App-facing channel object | **`Channel`** | — | RegionBook |
| Client instruction in a Result | **`op`** / builders `morph`, `toast` | — | action |
| Named server handler | **`action`** | — | op, region |
| IR request document | **`Intent`** | — | Result |
| IR response document | **`Result`** | — | Intent |
| Wire codecs JSON/CXB | **`wire`** package | — | capability |
| Application API app imports | **`ux_channel.api`** | root `ux_channel` exports | power packages |
| Cohesive code home | **`host` / `protocol` / …** packages | `zones.*` (navigation only) | “zone = implementation” |
| npm / JS island | **`Bridge`** | `bridges/*` | Region |
| Session/client/db guards API | **`state(ch)`** | `state_api` module | database driver |
| Agent tools façade | **`agents(ch)`** | `agents_api` | dual agent APIs |

---

## 2. Shared with Rust — **one name only** (Rust is source of truth)

Where both languages implement the same law, **Python uses Rust names**.
No second guess, no dual product speech.

| Rust | Python | Role |
|------|--------|------|
| `CapService` | `CapService` | Cap crypto service |
| `CapService::mint` | `CapService.mint` / `ch.mint` / `registry.mint` | Create cap |
| `CapService::verify` | `CapService.verify` | Verify cap |
| `CapService::hash_args` | `CapService.hash_args` | args_hash algorithm |
| `CapError` | `CapError` | Cap failure |
| `Intent` | `Intent` | Request IR |
| `ResultDoc` | `Result` | Response IR (same wire shape) |
| `encode_cxb` / `decode_cxb` | `wire` / `cxb` codecs | CXB |
| `HostRuntime` | `arch.HostRuntime` | Host kernel + runtime |
| `PeerApply` | `arch.PeerApply` | Peer kernel (apply Result, no DOM) |
| `PeerRuntime` | `arch.PeerRuntime` | Peer process wrapper |
| `Peer` | (not a twin — demo gate) | Classic Intent → cap → demo actions |
| `project` | `arch.project` | EffectGraph → ops |

Host-only types (no Rust twin) keep Python names: `Region`, `RegionBook`, `Channel`, …
`Peer` is the **classic HTTP demo gate**, not the peer kernel. Say **PeerApply** when you mean apply.

```python
from ux_channel import CapService, CapError, Intent, Result, Region, RegionBook

svc = CapService(secret)
token = svc.mint("Cart.add", {"sku": "a", "qty": 1})
svc.verify(token, action="Cart.add", args={"sku": "a", "qty": 1})
```

## 3. Package names vs module names (no shadowing)

Some packages avoid colliding with a module file name:

| Package folder | Why that name | Module you import for the core idea |
|----------------|---------------|-------------------------------------|
| `security/` | lives at `security/` (no top-level security.py) | `security.security` or shim `ux_channel.security` |
| `render/` | cannot be named `render/` (would shadow `render.py`) | morph/html live under `render/` |
| `realtime/` | cannot be named `media/` (would shadow `media.py`) | webrtc/sfu modules |

**Speech:** say “security package”, “render package”; imports may use plane suffix for physics of Python packaging.

Package paths keep `from ux_channel.security.security import safe_href` working.

---

## 4. Layers of speech (product → wire)

```text
Product speech     Region, mint cap, action, refresh
Type / API names   Region, RegionBook, CapService.mint
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
7. **AX** = `agents(ch)` only; **state** application API = `state(ch)` only.

---

## 6. Quick self-check

| If you say… | You should write… |
|-------------|-------------------|
| “this badge region” | `class Badge(Region)` or `@ch.region` |
| “refresh all registered slots” | `ch.regions` / RegionBook |
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


## Package names (professional)

| Package | Role | Not named |
|---------|------|-----------|
| `api` | Curated application exports | ~~api~~ |
| `host` | Channel, regions, state | — |
| `host.channel` | Channel implementation | ~~host.channel~~ |
| `protocol` | IR + caps | — |
| `render` | Morph / HTML / renderers | ~~paint~~ |
| `render.renderers` | HtmlRenderer stack | ~~paint.render~~ |
| `render.kit` | Demo/scaffold HTML helpers | ~~paint.demo~~ |
| `security` | Auth doors | ~~security~~ |
| `devtools` | Audit, CLI, observability | ~~devtools~~ |
| `bridge` | Contracts / scaffold | ~~bridge~~ |
| `bridges` | npm island presets | — |
| `catalog` | Package map navigator | ~~zones~~ |
| `host.patterns` | Composition patterns | ~~recipes~~ |
| `host.state_planes` | State plane helpers | ~~planes~~ |
| `protocol.json_codec` | JSON helpers | ~~json_codec~~ |

`Channel.describe()` replaces `describe()`. Caps use `mint` / `verify` only.


## Package and module names

| Name | Role |
|------|------|
| `api` | Curated application surface |
| `protocol` | Wire IR + CapService (mint/verify) |
| `host` | Channel, regions, actions |
| `host.channel` | Channel implementation module |
| `host.stores` | MemoryStateStore backends |
| `host.state_api` | Application `state()` API |
| `render` | Morph / HTML / renderers / kit |
| `wire` | encode/decode + CXB |
| `asgi` | mount_channel |
| `security` | CSRF, attenuate, limits |
| `devtools` | audit, CLI, dashboards |
| `bridge` / `bridges` | contracts / npm presets |
| `catalog` | Package navigator |

## Cap API (Rust-parity)

| Use | Do not use |
|-----|------------|
| `CapService.mint` | `.sign` |
| `CapService.verify` | — |
| `CapService.hash_args` | unsorted JSON |

## Public API constant names

| Constant | Module |
|----------|--------|
| `CHANNEL_PUBLIC_API` | `host.channel` |
| `WEBRTC_PUBLIC_API` | `host.channel` |
| `MEDIA_PUBLIC_API` | `realtime.media` |
| `BRIDGE_PUBLIC_API` | `bridge.bridge_plane` |


## Caller / runtime names

| Name | Kind | Notes |
|------|------|-------|
| `agents()` | Function | Application AX façade |
| `agent_runtime` | Package | AgentRunner + policy + session + peer |
| `guest_runtime` | Module under `bridge` | Island seal — not top-level |
| `mcp` | Package | Transport; uses agent_runtime |
| `workplace` | Package | Rooms/tickets — not agent kernel |


## Catalog / audit names

| Name | Means |
|------|--------|
| `catalog/` package | Package navigator |
| `host.action_catalog` | `action_catalog(registry)` |
| `agent_runtime.tool_audit` | Tool-call audit for agents |
| `devtools.audit` | `attach_audit` Intent log |
| `ChannelTest(mint_cap=True)` | Auto-mint caps in tests (not `sign=`) |
