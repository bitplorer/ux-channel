# Documentation map

Read in this order unless you already know the stack.

## Start here

| Doc | Audience |
|-----|----------|
| [README.md](README.md) | Repo overview |
| [python/README.md](python/README.md) | Python host — packages + imports |
| [python/STABILITY.md](python/STABILITY.md) | Layout law (no shims) |
| [NAMING.md](NAMING.md) | Intent ↔ name (Rust-parity caps) |
| [rust/README.md](rust/README.md) | Rust peer |

## Concepts

| Doc | Topic |
|-----|-------|
| [python/ONTOLOGY.md](python/ONTOLOGY.md) | Region / Bridge / Action |
| [TERMINOLOGY.md](TERMINOLOGY.md) | Glossary |
| [SPEC/](SPEC/) | Wire law |
| [conformance/](conformance/) | Shared vectors |

## Ops

| Doc | Topic |
|-----|-------|
| [OPERATIONAL.md](OPERATIONAL.md) | Verify / CI |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System shape |
| [FAQ.md](FAQ.md) | Common questions |
| [python/docs/start/](python/docs/start/) | Day-1 encyclopedia |

## Import cheat-sheet

```python
from ux_channel.day1 import Channel, Region, CapService, state
from ux_channel.protocol import CapService, Intent, Result, morph, toast
from ux_channel.host import Channel, Region, RegionBook
```
