# Enhancement Waves A–G — implementation map

Branch: `enhance/waves-a-g-peer-ir`

| Wave | Package / file | Status |
|------|----------------|--------|
| A Structured Ops | `python/src/ux_channel/ops/` | landed |
| B Continuations | `enhance/continuations.py` + `static/ux-peer-continuations.js` | landed |
| C Peer IR perception | **`static/ux-peer-perception.js` (SEPARATE)** | landed |
| D Negotiation | `enhance/negotiation.py` | landed |
| E Causal spine | `enhance/causal.py` | landed |
| F Differential ops | `enhance/delta.py` + delta drivers in kernel | landed |
| G Session recorder | `enhance/recorder.py` | landed |

## Separation invariant (Wave C)

```
ux-peer-kernel.js          → authority apply only
ux-peer-perception.js      → perception attach() wrapper
ux-peer-continuations.js   → slot-fill only
```

Kernel documents companions; perception never inlined.

## Tests

```bash
cd python && PYTHONPATH=src python -m pytest tests/gate/test_enhance_waves.py -q
```

## Non-goals in this branch

- No hard dependency on cek-surface
- No root `__all__` growth
- No Cap mint on Peer
- No breaking classic IR 0.1
