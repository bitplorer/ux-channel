# Python layout

Canonical law: [STABILITY.md](STABILITY.md) · Mental model: [../MENTAL_MODEL.md](../MENTAL_MODEL.md)

```text
App → api/ or root
        ↓
 protocol · host · render · security · wire · asgi · …
```

```python
from ux_channel import Channel, Region, CapService, state
from ux_channel.host.channel import Channel
from ux_channel.protocol import CapService
from ux_channel.host.stores import MemoryStateStore
```

```bash
python3 scripts/sync_python_layout.py --check
make verify
```
