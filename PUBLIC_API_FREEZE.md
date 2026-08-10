# Public API Freeze List — ux-channel 0.1

**Goal:** The surface that application authors and peer implementers may rely on.  
Aligned with package `docs/start/FREEZE_0.1.md` and `docs/start/API_SURFACE.md`.  
Everything not listed here is internal or explicit submodule and may change without a major version bump.

---

## 1. Day-1 core (frozen — do not rename)

```python
from ux_channel import (
    Channel, ChannelConfig, Region,
    agents, state, attach_audit,
    Intent, Result, ErrorObject,     # protocol types
    CapError, CapService,
)
from ux_channel.wire import encode, decode, dumps, loads, configure_wire
from ux_channel.ops import (         # public op builders
    morph, toast, navigate, push_url, swap, remove,
    set_attr, set_text, signal_set, clear_errors,
    focus, scroll, reload, noop,
)
```

| API | Role |
|-----|------|
| `Channel.boot` | One call → registry + HTTP mount + façade |
| `@ch.region` / `@ch.on` | Morph region + action |
| `ch.control(...)` | Signed attrs (cap mint) |
| `ch.done` / `ch.fail` / `ch.refresh` | Result verbs |
| `ch.scripts()` / `ch.body_attr_string(...)` | Client runtime tags |
| `ch.draft` | Ephemeral UI state |
| `ch.webrtc` | P2P plane |
| `ch.diagnose()` | Health (no secrets) |
| `agents(ch)` | AX tools / situation / dispatch |
| `state(ch)` | Session / client / db guards |
| `attach_audit(ch)` | Intent log + forensics |

**Rule:** Root `__all__` stays tiny. Bridges, redis, MCP, demo helpers, inspector stay off the root.

---

## 2. Channel construction & config

- `Channel.boot(app, config=...)`
- `ChannelConfig.development(...)` / `.production(...)` / `.from_env()`
- Environment variables prefixed **`UX_CHANNEL_`** only
- Production store requirements (nonce, idempotency, state) as documented

---

## 3. Wire & protocol

- Intent / Result / ops vocabulary with `"v": "1"`
- Media types: `application/ux-channel+json` (floor), `application/ux-channel+cxb`
- `encode` / `decode` / `dumps` / `loads` / `configure_wire`
- Caps, CSRF headers

CXB frame details live in package `docs/core/CXB.md` (already treated as normative).

---

## 4. Capability surface

- `ch.control` (primary mint path for apps)
- `CapService` public mint / verify
- `CapError`
- Documented attenuation helpers (`ux_channel.attenuate`)

---

## 5. Power speech (stable import-by-concern, not on root)

| Concept | Canonical import |
|---------|------------------|
| Quantity | `from ux_channel.quantity import Quantity` |
| I/O channel | `from ux_channel.io_channel import IoGate, IoRoomClaim` |
| Workplace / mesh | `from ux_channel.workplace import workplace, issue_mesh_membership` |
| Morph IR | `from ux_channel.morph_ir import ...` |
| Nested caps | `from ux_channel.attenuate import attenuate` |

These are frozen *names*; they are not required for day-1 apps.

---

## 6. Explicitly **not** public (may move or change)

- `ux_channel.demo` (training wheels only)
- Bridge scaffold / preset generators
- Inspector / DX-only endpoints and dashboards
- Redis / push-bus internals
- Native CXB `.so` loading details
- Test-only helpers and peer stubs used only in tests

---

## 7. Freeze process

1. This list is reviewed against the package (`__init__.py`, FREEZE_0.1.md, API_SURFACE.md).
2. Names taught in tutorials become public or are removed from tutorials.
3. After the 0.1 tag: additions are fine; removals or signature changes of listed items require a major version or documented deprecation window.

**Allowed without unfreeze:** bugfixes, docs, tests, new adapters/examples, additive optional kwargs with safe defaults, new power modules under import-by-concern.

**Requires major / explicit unfreeze:** renaming day-1 verbs, second agent product API, drivers in core, breaking wire `v` / op names.

---

## Linked documents

- Package: `docs/start/FREEZE_0.1.md`, `docs/start/API_SURFACE.md`, `docs/start/PRINCIPLES.md`
- `SPEC/intent-result-ops.md`, `SPEC/capability.md`
- Package `docs/core/WIRE.md`, `docs/core/RESULT.md`, `docs/core/CXB.md`
