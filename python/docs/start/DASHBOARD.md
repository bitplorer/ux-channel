# DX Dashboard — use cases & integrity

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |

## What it is for

Not product UI. An **observe-only operator snapshot** of a Channel.

| # | Use case | Question | Shows |
|---|----------|----------|--------|
| 1 | **Status** | Can I trust this process right now? | ok · env · summary |
| 2 | **Guidance** | What should I fix next? | doctor hints / next |
| 3 | **Performance** | Is the hot path within budget? | p50/p95/p99 **only if sampled** |
| 4 | **Inventory** | What surface is registered? | actions · regions · path · media |
| 5 | **Policy** | Are safety defaults sane? | require_cap · memory stores · serde · concurrency |
| 6 | **Observability** | Are OTel / channel traces flowing? | attach · recent frames (no payloads) |
| 7 | **Subsystems** | Bridge / media / webrtc quiet? | shallow diagnose digests |
| 8 | **Extensions** | Team-specific metrics? | your plugins only |

## Integrity

* Observe only — never mutates Channel  
* No secrets (secret-like keys redacted)  
* Missing performance is labeled — never fake zeros  
* **`sections`** in `dashboard.json` are the source of truth  
* HTML shell is optional (`shell="none"`)

## Architecture

```text
doctor + latencies + runtime
        ↓
   sections (use cases)
        ↓
   panels (presentation) + optional team extensions
        ↓
   shell HTML  ·or·  consume JSON yourself
```

## Day-1

```bash
uxchannel dashboard
```

Live thin view (dev): `GET /ux-channel/dx` — status/inventory without profile samples.

## Extend (team data only)

```python
from ux_channel.ops_dx.dx_dashboard import Widget, register_plugin

class Cost:
    id = "team.cost"
    order = 50
    def contribute(self, ctx):
        # ctx.sections already has status/performance/…
        return [Widget("team.cost", "Cost", props={"budget_ms": 5})]

register_plugin(Cost())
```

Do **not** re-implement Status/Guidance in extensions — read `ctx.sections` if needed.

## Model schema

Field ``schema`` on ``dashboard.json`` is **``DASHBOARD_MODEL_SCHEMA``** (currently **1**).

It versions the **dashboard snapshot JSON shape** only — not the Channel Intent/Result
protocol, not a migration from pre-0.1 drafts. Bump when panels/sections keys break.
