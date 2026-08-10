"""Runnable counter demo — no ux-dom required.

  uvicorn examples.counter.app:app --reload --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import ActionRegistry, Result, morph, toast
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.config import ChannelConfig
from ux_channel.html import action_attrs

cfg = ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!")
reg = ActionRegistry.from_config(cfg)


def counter_html(n: int) -> str:
    target = '[data-channel-id="Counter:root"]'
    cap_inc = reg.mint("Counter.inc", {"n": n})
    cap_dec = reg.mint("Counter.dec", {"n": n})
    return f"""<div data-channel-id="Counter:root" class="counter" style="display:flex;gap:.75rem;align-items:center;font:20px system-ui">
  <button type="button" {action_attrs("Counter.dec", args={"n": n}, cap=cap_dec, target=target)}>−</button>
  <span style="min-width:2rem;text-align:center">{n}</span>
  <button type="button" {action_attrs("Counter.inc", args={"n": n}, cap=cap_inc, target=target)}>+</button>
</div>"""


@reg.action("Counter.inc")
async def inc(n: int = 0) -> Result:
    # async handler supported
    return Result.success(
        morph(target='[data-channel-id="Counter:root"]', html=counter_html(n + 1)),
    )


@reg.action("Counter.dec")
def dec(n: int = 0) -> Result:
    return Result.success(
        morph(target='[data-channel-id="Counter:root"]', html=counter_html(n - 1)),
    )


@reg.action("Counter.reset")
def reset() -> Result:
    return Result.success(
        morph(target='[data-channel-id="Counter:root"]', html=counter_html(0)),
        toast("Reset", level="info"),
    )


@reg.before
def audit(intent, args):
    # example hook — return None to continue
    return None


app = FastAPI(title="uxchannel counter")
mount_channel(app, reg, path="/ux-channel", config=cfg)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    reset_cap = reg.mint("Counter.reset", {})
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>uxchannel counter</title>
  <script src="/ux-channel/static/ux-channel.js" defer></script>
  <script src="/ux-channel/static/ux-bridge.js" defer></script>
  <script src="/ux-channel/static/ux-inspector.js" defer></script>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 32rem; margin: 3rem auto; padding: 0 1rem; }}
    h1 {{ font-size: 1.25rem; }}
    .hint {{ color: #64748b; font-size: .9rem; margin-top: 1.5rem; }}
    button.uid-busy {{ opacity: .6; }}
  </style>
</head>
<body data-channel-endpoint="/ux-channel/action" data-channel-dev data-channel-inspector>
  <h1>Uid Channel — counter</h1>
  <p>Intent → Action → Result(ops) · server-driven UI</p>
  {counter_html(0)}
  <p style="margin-top:1rem">
    <button type="button" {action_attrs("Counter.reset", args={{}}, cap=reset_cap)}>Reset</button>
  </p>
  <p class="hint">Click ± — no full page reload. Dev strip shows action latency.</p>
</body>
</html>"""
