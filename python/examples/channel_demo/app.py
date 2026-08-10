"""Channel DX façade demo — minimal boilerplate counter + form patterns.

  uvicorn examples.channel_demo.app:app --reload --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel
from ux_channel.paint.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)

app = FastAPI(title="uxchannel Channel DX demo")
ch = Channel.boot(app, secret="dev-secret-key-32chars-minimum!!!!")


def counter_view(n: int) -> str:
    return ch.wrap(
        "Counter:root",
        (
            f'<span style="min-width:2rem;display:inline-block;text-align:center">{n}</span> '
            f'{demo_button(ch, "−", "Counter.dec", trust={"n": n}, target="Counter:root")} '
            f'{demo_button(ch, "+", "Counter.inc", trust={"n": n}, target="Counter:root")}'
        ),
        style="display:flex;gap:.75rem;align-items:center;font:20px system-ui",
    )


@ch.action("Counter.inc")
def inc(n: int = 0):
    return ch.patch("Counter:root", counter_view(n + 1), notice=f"{n + 1}")


@ch.action("Counter.dec")
def dec(n: int = 0):
    return ch.patch("Counter:root", counter_view(n - 1))


@ch.action("Counter.reset")
def reset():
    return ch.patch("Counter:root", counter_view(0), notice="Reset", notice_level="info")




# --- 0.6 naming: region + on + trust (alongside action/patch above) ----------

@ch.region
def named_badge(ctx):
    return f"<em>draft n={ch.draft.get('n', 0)}</em>"


@ch.on(refresh=[named_badge])
def named_inc():
    ch.draft.set("n", int(ch.draft.get("n", 0)) + 1)
    return ch.done(notice="named_inc")


@app.get("/", response_class=HTMLResponse)
def index():
    body = f"""
  <h1>Channel façade</h1>
  <p>Common patterns: <code>ch.button</code>, <code>ch.refresh</code>, <code>ch.page</code></p>
  {counter_view(0)}
  <h2>Region + on + trust</h2>
  {ch.html(named_badge)}
  <p>{demo_button(ch, "+ draft", named_inc)}</p>
  <p style="margin-top:1rem">{demo_button(ch, "Reset", "Counter.reset")}</p>
"""
    return demo_page(ch, body, title="Channel demo", dev=True, inspector=True)
