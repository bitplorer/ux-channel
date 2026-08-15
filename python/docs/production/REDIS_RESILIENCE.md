<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Redis connection failure handling

## ResilientRedis

```python
from ux_channel.redis_extra.resilience import ResilientRedis, RedisUnavailable

rr = ResilientRedis(url, soft_fail=True, cooldown_s=2, max_failures=3)
rr.execute(lambda r: r.ping(), default=False)
```

| Behavior | Default |
|----------|---------|
| Connection error | count failure, clear client |
| ≥ max_failures | circuit open for `cooldown_s` |
| soft_fail | return `default` instead of raise |
| Intent log | falls back to process-local buffer |
| Intent sync publish | returns 0, local handlers still fire |
| Push publish | local queues still receive |

## Health

```python
log = RedisIntentLog(url)
assert log.healthy()  # ping via ResilientRedis
```
