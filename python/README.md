# Python host package (ux-channel 0.1.0)

**Best of both worlds:** classic product layout from the release (`src/`, full `docs/`, `tests/`, `examples/`) **plus** monorepo enhancements (zones, day1, sorted `args_hash`, gate tests, Rust interop).

**Region** = one DOM slot · **RegionBook** = registry (`ch.regions`) · not a rename.

## Open this way (do not alphabet-scroll `src/ux_channel`)

| Doc | Purpose |
|-----|---------|
| **[LAYOUT.md](LAYOUT.md)** | Every module → **zone** (intent map) |
| **[ONTOLOGY.md](ONTOLOGY.md)** | Region vs Bridge vs Action |
| **[STRUCTURE.md](STRUCTURE.md)** | Permanent vs moving |
| [docs/start/](docs/start/) | Full day-1 encyclopedia (from release) |
| [docs/regions/](docs/regions/) | Region recipes |

```python
# Apps (day-1)
from ux_channel.day1 import Channel, Region, state

# Cohesive packages (preferred for libraries/extensions)
from ux_channel.host.dx import Channel
from ux_channel.protocol.capability import CapabilityService

# Explore
from ux_channel.zones import host, protocol
print(host.help())
```

```bash
export PYTHONPATH="$PWD/python/src${PYTHONPATH:+:$PYTHONPATH}"
```

## Tree (merged layout)

```text
python/
  src/
    ux_channel/
      protocol/ host/ paint/ security_plane/ …  # cohesive packages
      wire/ asgi/ bridges/ …                     # focused subpackages
      *.py                                      # legacy shims (stable)
    ux_channel_ux_dom/    # optional ux-dom glue
  docs/                   # full domain docs (start, regions, bridges, …)
  tests/
    gate/                 # monorepo CI gate (always run)
    core/ regions/ …      # full suite from release (optional extras)
  examples/               # product examples from release
  scripts/                # package maintenance scripts
  LAYOUT.md ONTOLOGY.md STRUCTURE.md
```

## Tests

```bash
# Always (CI / make verify) — no FastAPI required
make test-python

# Full release suite (needs extras: fastapi, httpx, …)
PYTHONPATH=python/src pytest python/tests -q --ignore=python/tests/gate
```

## Relation to Rust

Shared law: repo `../conformance/` + `../SPEC/`.  
`make verify` runs Python gate + Rust. Cross-mint: `make verify-http`.
