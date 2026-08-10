# DX dashboard example (use-case snapshot)

## Run

```bash
cd ux-channel
PYTHONPATH=src python examples/dx_dashboard/run.py
```

Open `reports/dx-example/dashboard.html` (and `dashboard.json`).

## What you see (in order)

| Use case | Content |
|----------|---------|
| Status | healthy / env summary |
| Guidance | doctor hints |
| Performance | p95/p50 (from profile suite) |
| Inventory | path · actions · regions |
| Policy | safety + serde/concurrency defaults |
| Subsystems | shallow diagnose digests |
| Extension | `TeamOverview` sample widgets |

## Extend

```python
from ux_channel.devtools.dashboard import register_plugin
from team_plugin import TeamOverview

register_plugin(TeamOverview())
# then: uxchannel dashboard
```

No asset paths, no JS CE definitions — data only.
