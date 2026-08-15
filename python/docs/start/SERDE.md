<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# JSON helpers

JSON encode/decode lives on the **wire** plane.

```python
from ux_channel.wire import dumps, loads, configure_wire, get_codec, available_engines

configure_wire(engine="auto")     # orjson → ujson → stdlib
configure_wire(engine="stdlib")
s = dumps({"ok": True})
```

`ux_channel.serde` re-exports the same helpers for internal modules that only need JSON text.

Env: `UX_CHANNEL_WIRE_ENGINE`

Format selection (json / msgpack / cxb): `configure_wire(format=...)`.
