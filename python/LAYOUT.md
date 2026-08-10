# Python layout

See [STABILITY.md](STABILITY.md).

```text
App  →  api/  or  root exports
         │
         ▼
 protocol/   host/   render/   security/   transport/   …
   Cap*       Channel  morph     CSRF        batch
   Intent     Region   HTML      limits      push
   ops        state    renderers
```

| Package | Intent |
|---------|--------|
| `api` | Application surface |
| `protocol` | IR + caps (Rust-parity) |
| `host` | Channel, regions, actions, state |
| `render` | Morph / HTML / placement / renderers |
| `security` | Auth doors / limits |
| `transport` | Streaming helpers |
| `foundations` | Quantity / provenance / io |
| `realtime` | WebRTC |
| `bridge` | Bridge contracts |
| `bridges` | npm presets |
| `devtools` | DX tooling / audit / CLI |
| `catalog` | Package navigator |

```python
from ux_channel import Channel, Region
from ux_channel.host.channel import Channel
from ux_channel.protocol import CapService
from ux_channel.render.renderers import HtmlRenderer
```
