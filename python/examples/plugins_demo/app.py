from ux_channel.bridge.bridge_api import mount_html, mount_ops, update_ops, register_simple_manifest
"""
Multi-library plug-and-play demo.

Shows:
  - create_channel factory
  - PluginHub bridge manifest
  - mount_html + bridge ops
  - custom HtmlRenderer for a toy \"dataframe\" object
  - ux-bridge.js simple sparkline adapter (no Chart.js CDN required)

  uvicorn examples.plugins_demo.app:app --reload --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import (
    Result,
    create_channel,
    morph,
    mount_ops,
    register_simple_manifest,
    toast,
    update_ops,
)
from ux_channel.paint.html import action_attrs
from ux_channel.paint.render import ChainRenderer, HtmlRenderer, StringRenderer

# ---------------------------------------------------------------------------
# Toy \"library\" object — stands in for pandas/polars/ux-dom in real apps
# ---------------------------------------------------------------------------


@dataclass
class TinyTable:
    """Pretend third-party table type an action might return."""

    rows: list[tuple[str, float]]


class TinyTableRenderer:
    """
    Plug-and-play renderer: ActionRegistry does not know TinyTable;
    the renderer teaches Channel how to HTML-encode it.
    """

    def render(self, value):
        if not isinstance(value, TinyTable):
            return None
        cells = "".join(
            f"<tr><td>{a}</td><td style='text-align:right'>{b:.1f}</td></tr>"
            for a, b in value.rows
        )
        return (
            f'<table data-channel-id="SalesTable:root" class="tbl">'
            f"<thead><tr><th>Day</th><th>Rev</th></tr></thead>"
            f"<tbody>{cells}</tbody></table>"
        )


# ---------------------------------------------------------------------------
# App bootstrap via factory (host + registry)
# ---------------------------------------------------------------------------

app = FastAPI(title="uxchannel plugins demo")
reg, hub = create_channel(
    secret="dev-only-change-me",
    app=app,
    host="fastapi",
    expose_internal_errors=True,
)

# Stack custom renderer in front of defaults from hub
reg._renderer = ChainRenderer(TinyTableRenderer(), StringRenderer())  # noqa: SLF001

# Declare npm bridge contract (client adapter registered in page script)
register_simple_manifest(
    "sparkline",
    methods=("update", "destroy"),
    events=("uid:spark-click",),
    description="Minimal canvas sparkline for demos",
    hub=hub,
)


def page_html(series: list[float], table: TinyTable) -> str:
    spark_props = {"values": series, "color": "#2563eb"}
    spark = mount_html(
        "spark1",
        package="sparkline",
        props=spark_props,
        class_name="spark",
        inner="<canvas width='320' height='80'></canvas>",
    )
    # Render table via our plugin renderer through encode path would need action;
    # for SSR first paint, call renderer directly:
    tbl = TinyTableRenderer().render(table)
    cap = reg.mint("Dashboard.refresh", {})
    return f"""
<div id="dash" data-channel-id="Dashboard:root">
  <h2>Sales</h2>
  {spark}
  <div id="table-slot">{tbl}</div>
  <p>
    <button type="button" {action_attrs("Dashboard.refresh", args={{}}, cap=cap, target='[data-channel-id="Dashboard:root"]')}>
      Refresh data
    </button>
  </p>
</div>
"""


@reg.action("Dashboard.refresh")
def refresh():
    """
    Returns multi-plane Result: morph HTML + bridge.update + toast.

    Demonstrates document plane + bridge plane in one response — the key
    advanced Channel capability vs HTML-only hypermedia.
    """
    import random

    series = [random.uniform(4, 20) for _ in range(12)]
    table = TinyTable(rows=[(f"D{i+1}", series[i]) for i in range(6)])
    html = page_html(series, table)
    return Result.success(
        morph(target='[data-channel-id="Dashboard:root"]', html=html),
        *update_ops("spark1", {"values": series, "color": "#2563eb"}),
        toast("Dashboard updated", level="success"),
    )


@app.get("/", response_class=HTMLResponse)
def index():
    series = [8, 10, 7, 14, 12, 16, 9, 11, 15, 13, 17, 12]
    table = TinyTable(rows=[(f"D{i+1}", series[i]) for i in range(6)])
    body = page_html(series, table)
    # First paint also needs bridge.mount so the canvas initializes
    # We embed mount via data attributes; ux-bridge scan handles it.
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>uxchannel plugins</title>
  <script src="/ux-channel/static/ux-channel.js" defer></script>
  <script src="/ux-channel/static/ux-bridge.js" defer></script>
  <script>
    // Plug-and-play bridge adapter (would live in a package in real apps)
    document.addEventListener("DOMContentLoaded", function () {{
      uxBridge.register("sparkline", {{
        mount: function (el, props) {{
          var canvas = el.querySelector("canvas") || el.appendChild(document.createElement("canvas"));
          canvas.width = 320; canvas.height = 80;
          var state = {{ props: props || {{ values: [] }} }};
          function draw() {{
            var ctx = canvas.getContext("2d");
            var vals = state.props.values || [];
            ctx.clearRect(0,0,canvas.width,canvas.height);
            if (!vals.length) return;
            var min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
            var pad = 4;
            ctx.strokeStyle = state.props.color || "#2563eb";
            ctx.lineWidth = 2;
            ctx.beginPath();
            vals.forEach(function (v, i) {{
              var x = pad + i * (canvas.width - pad*2) / Math.max(vals.length-1,1);
              var y = canvas.height - pad - ((v-min)/(max-min||1)) * (canvas.height-pad*2);
              if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
            }});
            ctx.stroke();
          }}
          draw();
          return {{
            update: function (p) {{ state.props = p; draw(); }},
            destroy: function () {{}}
          }};
        }},
        update: function (handle, props) {{
          if (handle && handle.update) handle.update(props);
        }},
        call: function (handle, method, args) {{
          if (handle && handle[method]) return handle[method].apply(handle, args||[]);
        }}
      }});
      uxBridge.scan(document);
    }});
  </script>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 36rem; margin: 2rem auto; padding: 0 1rem; }}
    .spark {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: .5rem; display: inline-block; }}
    .tbl {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    .tbl th, .tbl td {{ border-bottom: 1px solid #e2e8f0; padding: .4rem .5rem; text-align: left; }}
    .hint {{ color: #64748b; font-size: .9rem; }}
  </style>
</head>
<body data-channel-endpoint="/ux-channel/action" data-channel-dev>
  <h1>Uid Channel — plugins / multi-library</h1>
  <p class="hint">Custom renderer (TinyTable) + sparkline bridge host + factory bootstrap.</p>
  {body}
</body>
</html>"""
