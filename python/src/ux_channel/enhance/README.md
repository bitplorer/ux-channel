# enhance/ — optional Waves A–G plane

Additive envelopes and host runtime wiring. **Not** on root `ux_channel` exports.

## Host

```python
from ux_channel import Channel
ch = Channel.boot(app, secret="…")  # attaches ch.enhance automatically

# PeerHello (also available as POST /ux-channel/hello)
ch.enhance.accept_hello(session_id, {"surfaces": ["dom.morph", "dom.toast"], "features": ["continuations"]})

# Real continuation Cap
cont = ch.enhance.mint_continuation(event="http.response", action="Search.done", args={"q": "x"})
result_dict = ch.enhance.with_continuations(result.to_dict(), [cont])
```

Opt-out: `ChannelConfig` with `enhance=False`. Enable recorder: `enhance_record=True`.

## Client load order

```html
<script src="/ux-channel/static/ux-peer-kernel.js"></script>
<script src="/ux-channel/static/ux-peer-perception.js"></script>
<script src="/ux-channel/static/ux-peer-continuations.js"></script>
<script src="/ux-channel/static/ux-peer-dom-drivers.js"></script>
```

Perception is a **separate module**. Do not fold it into the kernel.

Static assets are served from `{path}/static/` by `mount_channel`.
