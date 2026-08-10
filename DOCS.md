# Documentation map

## Start

| Doc | Topic |
|-----|--------|
| [README.md](README.md) | Repo overview |
| [STRUCTURE.md](STRUCTURE.md) | Monorepo map |
| [python/README.md](python/README.md) | Python host |
| [python/STABILITY.md](python/STABILITY.md) | Layout + identity law |
| [NAMING.md](NAMING.md) | Intent ↔ name (Rust-parity caps) |
| [rust/README.md](rust/README.md) | Rust peer |

## Concepts

| Doc | Topic |
|-----|--------|
| [python/ONTOLOGY.md](python/ONTOLOGY.md) | Region / Bridge / Action |
| [TERMINOLOGY.md](TERMINOLOGY.md) | Glossary |
| [SPEC/](SPEC/) | Wire law |
| [conformance/](conformance/) | Golden vectors |

## Ops

| Doc | Topic |
|-----|--------|
| [OPERATIONAL.md](OPERATIONAL.md) | Verify / CI |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System shape |
| [FAQ.md](FAQ.md) | Common questions |
| [python/docs/start/](python/docs/start/) | Application encyclopedia |

## Import cheat-sheet

```python
from ux_channel import Channel, Region, CapService, state, morph
from ux_channel.api import Channel, Region, CapService, state

from ux_channel.protocol import CapService, Intent, Result, morph, toast
from ux_channel.host import Channel, Region, RegionBook
from ux_channel.host.stores import MemoryStateStore
from ux_channel.render import esc, morph_ir
from ux_channel.security import intent_headers, safe_href
from ux_channel.wire import encode, decode, encode_cxb
from ux_channel.asgi import mount_channel
from ux_channel.devtools import attach_audit
```

## Make targets

```text
make verify            # CI default
make layout            # package map / no shims
make test-python-gate  # interop + layout freeze
make test-python-host  # regions / state / core
make test-rust
```
