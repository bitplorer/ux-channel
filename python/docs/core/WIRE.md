# Wire codec (0.1)

Encode/decode channel **Intent** and **Result** documents.

## Defaults

| | |
|--|--|
| Format | **json** (browser + HTTP) |
| JSON engine | **auto** — orjson → ujson → stdlib |
| Binary | **opt-in** — `msgpack` · `cbor` · `cxb` |

```python
from ux_channel.wire import encode, decode, dumps, loads, configure_wire

configure_wire(format="json", engine="auto")  # default
blob = encode(result_dict)                    # WireBlob
doc = decode(blob.data)
s = dumps(doc)                                # always JSON text
```

Env: `UX_CHANNEL_WIRE`, `UX_CHANNEL_WIRE_ENGINE`, `UX_CHANNEL_WIRE_WORKERS` (batch).

## Formats

| Format | Media type | When |
|--------|------------|------|
| json | `application/ux-channel+json` | Application, browsers |
| msgpack | `application/ux-channel+msgpack` | Opt-in binary |
| cbor | `application/ux-channel+cbor` | Opt-in binary |
| **cxb** | `application/ux-channel+cxb` | Domain binary (Intent/Result/ops) |

## CXB

**Complete specification (leave nothing to guess):** **[CXB.md](./CXB.md)**

Includes: frame layout, wire types 0–11, Intent/Result tags, all 63 op dense keys,
string interning, CRC, CXBZ gates, ceilings, Python oracle vs Rust `.so` default,
HTTP usage, use cases, interoperability checklist, security, and source map.

```python
configure_wire(format="cxb")
blob = encode(result_dict)          # uses Rust _cxb_native when built
# force oracle: UX_CHANNEL_CXB_IMPL=python  or  encode_cxb_python(...)
```

Build accelerator: `./cxb_native/build.sh` · crate: `cxb_native/cxb_rs/`.

Also: [CXB_SPEED.md](./CXB_SPEED.md) · [CXB_REALWORLD.md](./CXB_REALWORLD.md) · [WIRE_BENCH.md](./WIRE_BENCH.md).


## Safety

- Soft configure (default): bad/missing format → JSON floor  
- Strict: `configure_wire(..., strict=True)` raises  
- `complete=True` (default): encode/decode recovery chain so work still ships  
- CXB: CRC, ceilings, per-call buffers, input snapshot  
- Batch: sequential default; `workers` opt-in (max 32)

## HTTP

Request body → `Content-Type`. Response → `Accept` (else policy, else JSON).  
Fallback response: `X-Channel-Wire-Fallback: 1`.

## Quality

| Suite | Path |
|-------|------|
| Conformance + live | `tests/core/test_wire_conformance_live.py` |
| Properties | `tests/core/test_wire_properties.py` |
| Fuzz | `scripts/fuzz_wire.py` |
| Bench | `scripts/bench_wire.py` → `WIRE_BENCH.md` |
| Ops future | `tests/core/test_wire_cxb_ops_future.py` |

```bash
pytest tests/core/test_wire_*.py -q
PYTHONPATH=src python scripts/fuzz_wire.py --seconds 10
PYTHONPATH=src python scripts/bench_wire.py --write docs/core/WIRE_BENCH.md
```
