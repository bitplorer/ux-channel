# Python host — single cohesive structure

No shims. No dual import paths for modules. **Packages by intent.**

## Apps

```bash
export PYTHONPATH="$PWD/python/src${PYTHONPATH:+:$PYTHONPATH}"
```

```python
from ux_channel.day1 import Channel, ChannelConfig, Region, CapService, state

ch = Channel.boot(secret="…")

class Badge(Region):
    def render(self, ctx):
        return f"<b>{self.ch.draft.get('n', 0)}</b>"
```

```python
# Caps — Rust names
svc = CapService(secret)
token = svc.mint("Cart.add", {"sku": "a", "qty": 1})
```

## Structure

| Package | Intent |
|---------|--------|
| **day1/** | App surface |
| **protocol/** | IR + CapService (Rust-parity) |
| **host/** | Channel, regions, state, actions |
| **paint/** | Morph / HTML / placement |
| **security/** | CSRF, limits, attenuate |
| **transport/** | batch / push / ws helpers |
| **foundations/** | quantity, provenance, io |
| **realtime/** | WebRTC / media |
| **wire/** **asgi/** **bridges/** … | Product planes |

Inventory: `src/ux_channel/PACKAGE_MAP.json`  
Rules: [STABILITY.md](STABILITY.md) · Concepts: [ONTOLOGY.md](ONTOLOGY.md) · Names: [../NAMING.md](../NAMING.md)

```bash
python3 scripts/sync_python_layout.py --check
make verify
make test-python-host
```
