# Intent sync (cross-worker)

**Foundations** (`ux_channel.intent_sync`). Product audit trail is still
`attach_audit` / intent log.

```python
from ux_channel.transport.intent_sync import attach_intent_sync

attach_intent_sync(ch, redis_url=url, on_sync=lambda m: ...)
```

With history + fan-out::

```python
from ux_channel.ops_dx.intent_log import attach_intent_log
from ux_channel.transport.intent_sync import attach_intent_sync

attach_intent_log(ch, redis_url=url)   # list history
attach_intent_sync(ch, redis_url=url)  # live fan-out
```

See [REDIS_RESILIENCE.md](../production/REDIS_RESILIENCE.md).
