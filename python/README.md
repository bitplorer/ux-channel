# Python host package (ux-channel 0.1.0 reference)

**This is where the full Python library lives.**

> **Confused about regions / bridges / state / actions?**  
> Start here → **[ONTOLOGY.md](ONTOLOGY.md)** · stability → **[STRUCTURE.md](STRUCTURE.md)**  
> Day-1 code: `from ux_channel.day1 import Channel, Region, …` (logical map of what is what and which import to use).  
> Then [docs/regions/REGIONS.md](docs/regions/REGIONS.md) for recipes.

```text
python/
  ux_channel/     ← main package (wire, caps, ASGI, bridges, …)
  ux_dom/         ← DOM surface helpers (if present)
  docs/core/      ← WIRE.md, CXB.md, …
  pyproject.toml  ← package metadata
```

## Two different “Python” locations in this repo

| Location | What it is | Size |
|----------|------------|------|
| **`python/ux_channel/`** | Full **host library** extracted from the 0.1.0 release | ~180 `.py` files |
| **`demos/python_forward/`** | Tiny **adapter** that POSTs Intent to the Rust peer | 1 script |
| **`conformance/harness/*.py`** | Stdlib validators for golden vectors | 3 scripts |

If you were looking for `CapabilityService`, `encode`/`decode`, ASGI mount, CXB oracle, etc. — that is under **`python/ux_channel/`**, not under `demos/` (that is only a thin forwarder).

## Quick map of `ux_channel/`

| Path | Role |
|------|------|
| `wire/` | JSON / msgpack / cbor / **CXB** codecs + **negotiate.py** |
| `wire/cxb.py` | Pure-Python CXB oracle |
| `capability.py` | Cap mint/verify (itsdangerous) |
| `asgi/` | HTTP/ASGI channel surface |
| `encode.py` | High-level encode helpers |
| `actions_file.py` / actions | Action registration patterns |
| `bridges/` | Bridge plane |
| `components/` | UI component helpers |

Normative wire docs: `docs/core/WIRE.md`, `docs/core/CXB.md`.

## Use on PYTHONPATH (no install)

```bash
# from package root (this repo)
export PYTHONPATH="$(pwd)/python:${PYTHONPATH:-}"

python3 -c "from ux_channel.wire import encode, decode; print('ok')"
python3 -c "from ux_channel.wire.cxb import encode_cxb, decode_cxb, is_cxb; print(is_cxb)"
```

Install editable (optional, needs deps from `pyproject.toml`):

```bash
cd python && pip install -e .
```

## Relation to Rust peer

```text
python/ux_channel   ── same IR + cap + CXB contract ──  rust
        │                                                      │
        │  full ASGI product host                              │  second implementation
        │  (this package)                                      │  + uxc_peer HTTP demo
        ▼                                                      ▼
demos/python_forward  ── thin POST Intent ──────────────────► uxc_peer
```

Law vectors: `../conformance/`. Human guides: `../TERMINOLOGY.md`, `../HOW_IT_WORKS.md`, `../REFERENCE.md`.

## Note on the zip

`ux-channel-0.1.0.zip` at repo root (gitignored) is the full release tarball (examples, tests, scripts).  
**Source for daily browsing is `python/`** so it is visible on GitHub without unzipping.

## Tests (monorepo gate)

```bash
# from repo root — also part of ./verify.sh / make verify
make test-python
# or:
PYTHONPATH=python pytest python/tests -q
```

These tests prove:
- interop with shared `conformance/` (same law as Rust)
- frozen public API + `day1` façade
- day-1 regions (morph uid, refresh, actions) without FastAPI

