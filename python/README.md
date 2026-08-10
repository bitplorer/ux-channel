# Python host (`ux-channel`)

Long-term layout: **implementations in cohesive packages**, **generated aliases** at the top level, **Rust-parity names** for shared cap/IR APIs.

## Start (apps)

```bash
export PYTHONPATH="$PWD/python/src${PYTHONPATH:+:$PYTHONPATH}"
```

```python
from ux_channel.day1 import Channel, ChannelConfig, Region, CapService, state

ch = Channel.boot(secret="…")  # or FastAPI app + ChannelConfig

class Badge(Region):
    def render(self, ctx):
        return f"<b>{self.ch.draft.get('n', 0)}</b>"

    @Region.action
    def add(self):
        self.ch.draft.set("n", self.ch.draft.get("n", 0) + 1)
```

Cap (same words as Rust):

```python
svc = CapService(secret)
token = svc.mint("Cart.add", {"sku": "a", "qty": 1})
svc.verify(token, action="Cart.add", args={"sku": "a", "qty": 1})
```

## Structure (no alphabet scrolling)

```text
src/ux_channel/
  PACKAGE_MAP.json     ← source of truth
  protocol/ host/ paint/ security_plane/ …
  wire/ asgi/ bridges/ …   ← product subpackages
  *.py                     ← GENERATED aliases (sync_python_layout.py)
  day1                     ← public app surface (via host.day1)
```

```bash
python3 scripts/sync_python_layout.py --check
from ux_channel.zones import help_public; print(help_public())
```

## Docs (few, durable)

| Doc | Why |
|-----|-----|
| **[STABILITY.md](STABILITY.md)** | How we stay maintainable |
| [LAYOUT.md](LAYOUT.md) | Packages + coupling |
| [ONTOLOGY.md](ONTOLOGY.md) | Concepts |
| [docs/start/](docs/start/) | Day-1 encyclopedia |
| [../NAMING.md](../NAMING.md) | Intent ↔ name |

## Tests

```bash
make verify             # gate + rust (required)
make test-python-host   # host regression (regions/state/day1)
```

## Rust

Shared law: repo `conformance/` + `CapService.mint/verify`. Host-only: regions, Channel, bridges, …
