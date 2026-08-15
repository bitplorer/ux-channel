# Enhancement Waves A\u2013G \u2014 implementation map

On `main` since PR #3. Activation layer: `feat/enhance-activation`.

| Wave | Package / file | Status |
|------|----------------|--------|
| A Structured Ops | `python/src/ux_channel/ops/` | landed |
| B Continuations | `enhance/continuations.py` + `static/ux-peer-continuations.js` | landed |
| C Peer IR perception | **`static/ux-peer-perception.js` (SEPARATE)** | landed |
| D Negotiation | `enhance/negotiation.py` + **`enhance/handshake.py`** | landed + host session |
| E Causal spine | `enhance/causal.py` | landed |
| F Differential ops | `enhance/delta.py` + delta drivers in kernel | landed |
| G Session recorder | `enhance/recorder.py` | landed |

## Activation (post-merge)

| Piece | Path |
|-------|------|
| Host handshake | `enhance/handshake.py` \u2192 `HandshakeRegistry.accept_hello` / `project_result` |
| Real DOM drivers | `static/ux-peer-dom-drivers.js` |
| Demo | `demos/enhance_search/` |
| Gate tests | `tests/gate/test_enhance_waves.py` + `test_enhance_handshake.py` |

## Separation invariant (Wave C)

```
ux-peer-kernel.js          \u2192 authority apply only
ux-peer-perception.js      \u2192 perception attach() wrapper  (SEPARATE file)
ux-peer-continuations.js   \u2192 slot-fill only               (SEPARATE file)
ux-peer-dom-drivers.js     \u2192 optional real DOM bindings   (SEPARATE file)
```

## Client load order

```html
<script src="/ux-channel/static/ux-peer-kernel.js"></script>
<script src="/ux-channel/static/ux-peer-perception.js"></script>
<script src="/ux-channel/static/ux-peer-continuations.js"></script>
<script src="/ux-channel/static/ux-peer-dom-drivers.js"></script>
```

```js
var kernel = uxcPeer.createPeerKernel({ drivers: uxcPeer.makeWebDrivers() });
var perc  = uxcPerception.attach(kernel, uxcPeerDom.perceptionOptions({ coalesceMs: 120 }));
var cont  = uxcContinuations.create({ submitIntent: postIntent });
```

## Host handshake

```python
from ux_channel.enhance import HandshakeRegistry

reg = HandshakeRegistry()
reg.accept_hello(session_id, peer_hello_dict)
result = reg.project_result(session_id, result)  # drops unsupported ops
```

## Tests

```bash
cd python && PYTHONPATH=src python -m pytest tests/gate/test_enhance_waves.py tests/gate/test_enhance_handshake.py -q
```

## Non-goals

- Optional extra `[cek]` (`ChannelConfig.cek = off \| adapt \| require`). Default remains **off** — today's path, zero `cek_host` / `cek_surface` imports. Native enhance code still exists behind off (Phase 1). Phase 2 deletes the clone only after the adapter critic SHIPs.
- No root `__all__` growth
- No Cap mint on Peer
- No breaking classic IR 0.1
