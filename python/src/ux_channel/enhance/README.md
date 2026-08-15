# enhance/ — optional Waves A–G plane

Additive envelopes and helpers. **Not** on root `ux_channel` exports.

```python
from ux_channel.ops import Op, plan, to_classic, macros
from ux_channel.enhance import (
    Continuation, attach_continuations,
    PeerHello, negotiate_ops,
    Trace, attach_trace,
    prefer_delta, region_hash,
    SessionRecorder, enhance_result, strip_unknown_for_classic,
)
```

## Client load order

```html
<script src="/ux-channel/static/ux-peer-kernel.js"></script>
<script src="/ux-channel/static/ux-peer-perception.js"></script>
<script src="/ux-channel/static/ux-peer-continuations.js"></script>
<script>
  var kernel = uxcPeer.createPeerKernel({ drivers: uxcPeer.makeWebDrivers() });
  var perc = uxcPerception.attach(kernel, { coalesceMs: 120 });
  var cont = uxcContinuations.create({
    submitIntent: function (intent) { /* POST /ux-channel/action */ }
  });
  // on Result:
  cont.armFromResult(result);
  kernel.applyResult(result); // perception clears shadows first
</script>
```

Perception is a **separate module**. Do not fold it into the kernel.
