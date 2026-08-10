# CXB speed strategy — safe × orders of magnitude

> **Normative wire format:** see **[CXB.md](./CXB.md)** for complete layout, backends, and use cases.


Goal: **never sacrifice surity** (CRC, ceilings, snapshot, recovery, intern budgets)
while unlocking **10–100×** on hot paths where it matters.

## Honest baseline (pure Python 0.1)

| Bottleneck | Why |
|------------|-----|
| Deep snapshot | Safety vs concurrent mutation — necessary unless caller opts in |
| Per-op Python loops | 40 toasts = 40× interpreter overhead |
| `typing.Mapping` checks | Extremely slow vs `type(x) is dict` |
| Frequency pass | Correct intern policy — skipped when ops < 2 |
| Freeform msgpack/json | Open maps — not schema-tight like protobuf |

**Protobuf-class µs** needs a **native** encoder/decoder. Python stays the reference + safety net.

---

## Strategy layers (innovate without gambling)

```text
┌─────────────────────────────────────────────────────────────┐
│ L0  Safety floor (always on)                                │
│     snapshot · CRC · ceilings · complete recovery · budgets │
├─────────────────────────────────────────────────────────────┤
│ L1  Python hot path (this release)                          │
│     type(x) is dict · no double-snapshot ops · skip intern  │
│     pass when useless · optional native seam                │
├─────────────────────────────────────────────────────────────┤
│ L2  Shape specialization (next)                             │
│     cache encoder for (kind, field tags, op-key sets)       │
│     immutable; race-safe; invalidate never (content-hash)   │
├─────────────────────────────────────────────────────────────┤
│ L3  Domain bulk encoding (next)                             │
│     "columnar ops": 40× toast → op once + columns           │
│     same decode surface; huge win on homogeneous Results    │
├─────────────────────────────────────────────────────────────┤
│ L4  Native accelerator `_cxb_native` (order-of-magnitude)   │
│     Rust/PyO3 or C; identical byte contract                 │
│     Python path if missing OR native raises                 │
├─────────────────────────────────────────────────────────────┤
│ L5  Trusted zero-copy mode (opt-in, explicit)               │
│     skip snapshot when caller passes frozen mapping         │
│     never default — host must opt in                        │
└─────────────────────────────────────────────────────────────┘
```

### Safety invariants (non-negotiable at every layer)

1. **Corrupt frames reject** (CRC / magic / ceilings) — no silent ops  
2. **Native failure → Python** — never fail closed on accelerator bugs  
3. **Default path snapshots** — concurrent mutation cannot tear frames  
4. **Intern cannot explode** — freq≥2, entry/byte budgets  
5. **JSON floor** remains application for browsers  
6. **complete recovery** still ships the document  

### L4 native contract (`cxb_native/` in-repo crate)

Build: ``./cxb_native/build.sh`` → ``ux_channel._cxb_native``.

### L4 native contract

```text
ux_channel._cxb_native.encode(dict) -> bytes   # CXB1/CXBZ + CRC
ux_channel._cxb_native.decode(bytes) -> dict
```

- Same magic, tags, intern, CXBZ gate semantics  
- Property tests + fuzz must pass against Python oracle  
- Install optional: `pip install ux-channel[cxb-native]` (future)

### L3 columnar ops (domain innovation vs protobuf)

Protobuf would need a new message type. CXB can add wire type **12 = op_batch**:

```text
op_batch: u8 op_name_intern | u8 ncol | col_keys… | nrows | cell…
```

Decode expands to the same list of op dicts — **zero API change** for clients.

### Expected gains

| Layer | Typical gain | Risk |
|-------|--------------|------|
| L1 Python hot path | 1.5–3× | Low |
| L2 shape cache | 2–5× steady-state | Low |
| L3 columnar bulk | 5–20× on homogeneous ops | Medium (new wire type) |
| L4 native | **10–100×** encode/decode | Medium (oracle tests) |
| L5 skip snapshot | 1.2–2× | Host discipline |

**Stacked L1+L3+L4** is how you approach “orders of magnitude” **and** stay sure.

### What not to do

- Drop CRC for speed  
- Global mutable intern tables  
- Silent native fallback that returns partial docs  
- Make CXB the browser default (JSON+orjson wins µs there)

### Reproduce

```bash
PYTHONPATH=src python scripts/bench_cxb_realworld.py
pytest tests/core/test_wire_cxb*.py tests/core/test_wire_complete.py -q
```
