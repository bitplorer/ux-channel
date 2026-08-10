# Foundations — organic modules

**Not AX.** Agent Experience is `agents(ch)` — [AGENTS.md](../agents/AGENTS.md).

**I/O stance:** uxchannel is a **capability-shaped I/O channel** (mesh-ready), **not** a device driver. Full constitution: [IO_CHANNEL.md](../workplace/IO_CHANNEL.md).

## Preferred imports

| Concern | Import |
|---------|--------|
| Store-grounded measure | `from ux_channel.foundations.quantity import Quantity` |
| **Workplace (rooms)** | `from ux_channel.workplace import workplace` |
| **I/O channel (not driver)** | `from ux_channel.foundations.io_channel import IoGate, IoProtocol, IoRoomClaim` |
| Reference adapters | `from ux_channel.io_adapters import ScannerAdapter, LightsAdapter, LabDutAdapter` |
| Nested caps | `from ux_channel.security.attenuate import attenuate` |
| Tree caps | `from ux_channel.security.tree_cap import TreeEnvelope` |
| Morph IR | `from ux_channel.paint.morph_ir import elem, region` |
| Projections | `from ux_channel.paint.projections import project_all` |
| Stable uids | `from ux_channel.paint.slot_compile import stable_uid` |
| Intent log / forensics | `attach_audit` · `intent_log` · `forensics` |
| Sealed bridge | `from ux_channel.bridge.bridge_protocol import SealedBridgeProtocol` |
| Guest runtime | `from ux_channel.bridge.guest_runtime import GuestRuntime` |
| Agent peer | `agents(ch).dispatch` · power: `ux_channel.agent_peer` |

```python
from ux_channel.foundations.quantity import Quantity
from ux_channel.foundations.io_channel import IoGate, IoProtocol, IoMethodSpec, IoKind, IoRoomClaim
from ux_channel.paint.morph_ir import elem, region

q = Quantity.from_store(3, "seats", source="db.booking.9.seats", revision=2)
tree = region("cart", elem("span", "3"))
```

## Laws

* **Quantity** — measure + provenance; never bare in client/session; prefer `from_store`.
* **I/O** — channel authorizes; adapters perform; mesh ≠ trust ([IO_CHANNEL.md](../workplace/IO_CHANNEL.md)).
* **region(uid)** — paint surface, not an HTML tag.
* **AX** — only `agents(ch)`.

See [LAYERS.md](../start/LAYERS.md) · [GLOSSARY.md](../start/GLOSSARY.md).

## Product physics

**Layering:** pure control-plane modules (not AX). Agent product API: `agents(ch)`.

## Quantity (store-grounded measure)

```python
from ux_channel.foundations.quantity import Quantity, QuantityError, QuantityBudget

# preferred — builds Provenance internally
amt = Quantity.from_store(10.5, "USD", source="db.order.9.amount", revision=3)
qty = Quantity.from_store(12, "units", source="db.sku.X.stock", revision=1)
dose = Quantity.from_store(5, "mg", source="ehr.rx.1.dose", revision=4)

budget = QuantityBudget(max_magnitude=10, unit="USD")
assert budget.allows(amt)
```

Session/client refuse bare numbers on quantity-ish paths. Use ids in chrome; load via `from_store`.

## Capability-shaped documents

```python
from ux_channel.security.tree_cap import TreeEnvelope, compile_tree_caps
```

## Agent ≡ button

```python
from ux_channel import agents
ag = agents(ch)
r = ag.dispatch("Cart.add", {"sku": "x"}, peer=ag.peer("bot-1"))
```

## Multi-surface Morph IR

```python
from ux_channel.paint.morph_ir import region, elem
from ux_channel.paint.projections import project_all

views = project_all(region("cart", elem("span", "3")))
```
