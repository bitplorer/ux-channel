# Public API — minimal cognitive load

> Full feature catalog: **[FEATURES.md](../FEATURES.md)**.


### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |



## Philosophy (non-negotiable)

1. **One façade:** `Channel` after `boot` — not five frameworks.
2. **Root is tiny:** protocol + Channel + regions. Layers stay submodules.
3. **ux-dom owns markup;** Channel owns control, trust, regions, ops.
4. **WebRTC application is `ch.webrtc`**, never a forest of free functions on root.
5. **Demo helpers ≠ product UI** — `button`/`page` are training wheels.
6. **AX ≠ foundations** — `agents(ch)` is product; quantity/IR modules are physics.
7. **Import by concern** — no grab-bag package.

```text
        ┌─────────────────────────────────────┐
        │  Application (learn once)                 │
        │  boot region on control scripts     │
        │  draft done fail webrtc             │
        │  agents(ch)  state(ch)  attach_audit│
        └─────────────────┬───────────────────┘
                          │
        ┌─────────────────▼───────────────────┐
        │  Power by concern                   │
        │  quantity io_channel attenuate morph_ir │
        └─────────────────┬───────────────────┘
                          │
        ┌─────────────────▼───────────────────┐
        │  Layers                             │
        │  scaffold webrtc agents MCP …       │
        └─────────────────────────────────────┘
```

Print the map anytime::

    from ux_channel import Channel
    print(Channel.describe())

Layer doc: [LAYERS.md](LAYERS.md) · Foundations: [FOUNDATIONS.md](../foundations/FOUNDATIONS.md).

## Application imports

```python
from ux_channel import Channel, ChannelConfig, Region, agents, state, attach_audit
```

| API | Role |
|-----|------|
| `Channel.boot` | One call → registry + HTTP mount + façade |
| `@ch.region` | Morph region |
| `@ch.on` | Action (+ optional refresh) |
| `ch.control(...)` | Signed attrs for your button/form |
| `ch.scripts()` | Client runtime tags |
| `ch.body_attr_string(...)` | Body data-* (SSE/WS/WebRTC) |
| `ch.draft` | Ephemeral UI state |
| `ch.done` / `ch.fail` / `ch.refresh` | Result verbs |
| `ch.webrtc` | P2P plane (tickets, paths) |
| `ch.diagnose()` | Health, no secrets |
| `agents(ch)` | **AX** — tools / situation / dispatch / effects |
| `state(ch)` | session / client / db guards |
| `attach_audit(ch)` | intent log + forensics façade |

## Foundations — organic modules

| Need | Import |
|------|--------|
| Quantity | `from ux_channel.foundations.quantity import Quantity` |
| I/O channel | `from ux_channel.foundations.io_channel import IoGate, IoProtocol, IoRoomClaim` |
| Workplace | `from ux_channel.workplace import workplace` |
| Nested caps | `from ux_channel.security.attenuate import attenuate` |
| Morph IR | `from ux_channel.render.morph_ir import elem, region` |
| Sealed guests | `from ux_channel.bridge.bridge_protocol import SealedBridgeProtocol` |
| Peer (tests) | `from ux_channel.agent_runtime.peer import dispatch_peer` |

### Quantity (canonical)

```python
from ux_channel.foundations.quantity import Quantity, QuantityBudget

q = Quantity.from_store(
    10.5, "USD",
    source="db.order.9.amount",
    revision=3,  # your store's row/field edition
)
# q.magnitude · q.unit · q.provenance
```

Never put `Quantity` or bare authority-ish numbers in client/session chrome.

Full map: [FOUNDATIONS.md](../foundations/FOUNDATIONS.md) · [GLOSSARY.md](GLOSSARY.md).

## Forbidden growth

* New root exports for every feature  
* Dual agent API  
* Treating Morph IR `project_agent` as AX world model  

## Tests

```bash
pytest -q
python scripts/_consistency_audit.py
```

## Concurrency (internal)

Not a application application API. Dispatch is thread-safe by default; apps use
``registry.dispatch`` / HTTP. Maintainers: ``scripts/profile_p95.py`` and
``docs/start/CONCURRENCY.md``.

