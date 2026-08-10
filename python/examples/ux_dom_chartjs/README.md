# ux-dom + uxchannel + Chart.js

Working stack: **ux-dom** page · **ux-channel** actions/regions/caps · **Chart.js** via **`ch.bridge`**.

## Architecture

```text
ux-dom Document / buttons
        │  ch.control(...).as_ux_dom()
        ▼
uxchannel ── regions (KPI morph)
             ── draft state
             ── Result ops: bridge.update / bridge.call
        │
        ▼
ux-bridge.js + chartjs-adapter.js  →  Chart.js 4 (CDN)
```

| Piece | Role |
|-------|------|
| `ch.control` | Signed button attrs |
| `@ch.on(refresh=[…])` | Actions + region morph |
| `ch.bridge.register` | Method allowlist |
| `ch.bridge.update_ops` | Push new series into the chart |
| `ch.bridge.call(..., package="chart.js")` | e.g. `setType` |
| `ux_channel.demo.script_tags(ch.runtime())` | Channel JS (no HTML as truth) |
| Adapter | Maps props → Chart.js |

## Run

```bash
cd /workspace/uxchannel pip install -e ".[fastapi]"   # if needed
# ux_dom on PYTHONPATH (or pip install ux_dom)
export PYTHONPATH=src:/workspace/ux_dom-improve

uvicorn examples.ux_dom_chartjs.app:app --host 0.0.0.0 --port 8080
```

Open the preview, then try:

1. **Reshuffle data** — new series + KPI morph + chart update  
2. **Nudge Friday** — single bar bump  
3. **Cycle theme** — indigo / emerald / rose  
4. **Bar → Line → Doughnut** — `bridge.call` `setType`  

## Key code

```python
ch.bridge.register("chart.js", methods=("update", "destroy", "setType"))

# host element (Placement attrs under the hood)
mount_html("rev-chart", package="chart.js", props=_chart_props(), …)

@ch.on(name="Dash.randomize", refresh=[kpi, meta])
def randomize():
    …  # mutate draft
    return Result(ok=True, ops=list(ch.done().ops) + ch.bridge.update_ops("rev-chart", props))
```

Without ux-dom the same app falls back to plain HTML + `ch.control(...).as_dict()`.
