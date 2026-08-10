# Python host — single cohesive structure

No shims. No dual import paths for modules. **Packages by intent.**

## Apps

```bash
export PYTHONPATH="$PWD/python/src${PYTHONPATH:+:$PYTHONPATH}"
```

```python
from ux_channel.api import Channel, ChannelConfig, Region, CapService, state

ch = Channel.boot(secret="…")

class Badge(Region):
    def render(self, ctx):
        return f"<b>{self.ch.draft.get('n', 0)}</b>"
```

```python
# By cohesive package
from ux_channel.protocol import CapService, Intent, Result, morph
from ux_channel.host import Channel, Region, RegionBook

# Caps — Rust names
svc = CapService(secret)
token = svc.mint("Cart.add", {"sku": "a", "qty": 1})
```

## Structure

| Package | Intent |
|---------|--------|
| **api/** | App surface |
| **protocol/** | IR + CapService (Rust-parity) |
| **host/** | Channel, regions, state, actions |
| **render/** | Morph / HTML / placement |
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

## Docs

**First time?** Start at [../START_HERE.md](../START_HERE.md).


See [docs/index.md](docs/index.md) for the full encyclopedia.

- [HOW_TO](docs/start/HOW_TO.md) · [GOLDEN_PATH](docs/start/GOLDEN_PATH.md) · [STABILITY](STABILITY.md) · [../MENTAL_MODEL.md](../MENTAL_MODEL.md)
