# Enhancement Waves A\u2013G \u2014 implementation map

Branch: `enhance/waves-a-g-peer-ir` \u00b7 PR: https://github.com/bitplorer/ux-channel/pull/3

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
ux-peer-kernel.js          \u2192 authority apply only
ux-peer-perception.js      \u2192 perception attach() wrapper  (SEPARATE file)
ux-peer-continuations.js   \u2192 slot-fill only               (SEPARATE file)
```

Kernel documents companions via `uxcPeer.companions`; perception never inlined.

## Client load order

```html
<script src="/ux-channel/static/ux-peer-kernel.js"></script>
<script src="/ux-channel/static/ux-peer-perception.js"></script>
<script src="/ux-channel/static/ux-peer-continuations.js"></script>
```

```js
var kernel = uxcPeer.createPeerKernel({ drivers: uxcPeer.makeWebDrivers() });
var perc  = uxcPerception.attach(kernel, { coalesceMs: 120 });
var cont  = uxcContinuations.create({ submitIntent: postIntent });
```

## Tests

```bash
cd python && PYTHONPATH=src python -m pytest tests/gate/test_enhance_waves.py -q
```

## Non-goals

- No hard dependency on cek-surface
- No root `__all__` growth
- No Cap mint on Peer
- No breaking classic IR 0.1
