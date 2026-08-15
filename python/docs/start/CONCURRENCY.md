<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Concurrency (internal behaviour)

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |

## For application developers

**You do not configure parallel or concurrency.**

Write normal code:

```python
ch = Channel.boot(app, config=ChannelConfig.development(secret="…"))
result = ch.registry.dispatch(intent)
# or HTTP / regions / controls as usual
```

The library already:

* Thread-safe registry and stores
* Optional bulkhead under load (when configured for the **host**, not per call)
* Safe sequential batch by default
* Internal parallel fan-out only where isolation is safe

Application DX never asks you to pick thread pools or parallel flags.

## For maintainers / tests only

`ux_channel.concurrency` and `ChannelConfig` parallel fields are host/ops
tuning, not application logic.

### Profiling (p95 + flamegraphs)

```bash
python scripts/profile_p95.py
# → reports/p95/report.html
# → reports/p95/profile.speedscope.json  (open in https://www.speedscope.app)
```

Tests: `tests/core/test_p95_profiling.py`.

## Profile (first-class DX)

```bash
uxchannel profile
uxchannel profile --out ./reports/p95 --json-report
```

Writes `reports/p95/report.html`, `latency.json`, and `profile.speedscope.json`
(open in speedscope.app). App source is never modified.
