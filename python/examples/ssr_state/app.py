"""
state() demo — session chrome + morph.

  uvicorn examples.ssr_state.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig, state
from ux_channel.paint.demo import attr_string, demo_button, script_tags

app = FastAPI(title="uid-state")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="ssr-state-demo-secret-key-32bytes!!",
        allow_memory_stores=True,
        require_cap=False,
    ),
)
st = state(ch)

count = st.session("count", 0)
cart = st.session("cart", {"qty": 0})


@st.region("badge")
def badge(ctx):
    return f'<span class="pill" data-channel-id="badge">items · {count()}</span>'


@st.region("cart")
def cart_view(ctx):
    c = cart()
    return (
        f'<div class="card" data-channel-id="cart">'
        f"<h2>Cart</h2><p class='val'>{c.get('qty', 0)} in cart</p>"
        f"<p class='muted'>count = {count()}</p></div>"
    )


@st.action
def add():
    count.add(1)
    cart.set(lambda c: {**(c or {}), "qty": int((c or {}).get("qty", 0)) + 1})


@st.action
def reset():
    count.set(0)
    cart.set({"qty": 0})


@app.get("/", response_class=HTMLResponse)
def index():
    rt = ch.runtime()
    body = ch.body_attrs()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>state()</title>
  {script_tags(rt)}
  <style>
    :root {{ color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; }}
    body {{ margin:0; background:#020617; color:#e2e8f0; }}
    main {{ max-width:40rem; margin:0 auto; padding:3rem 1.25rem; }}
    h1 {{ letter-spacing:-.03em; }}
    .row {{ display:flex; gap:.75rem; flex-wrap:wrap; margin:1.5rem 0; align-items:center; }}
    .pill {{ background:#1e293b; border:1px solid #334155; padding:.35rem .75rem;
      border-radius:999px; font-weight:600; }}
    .card {{ background:#0f172a; border:1px solid #1e293b; border-radius:1rem; padding:1.25rem; }}
    .val {{ font-size:2rem; font-weight:700; margin:.25rem 0; }}
    .muted {{ color:#94a3b8; font-size:.9rem; }}
    button {{ border:0; border-radius:.75rem; padding:.65rem 1rem; font-weight:600;
      background:linear-gradient(135deg,#8b5cf6,#06b6d4); color:white; cursor:pointer; }}
    code {{ color:#a5b4fc; }}
    pre {{ background:#0f172a; border:1px solid #1e293b; border-radius:.75rem; padding:1rem; overflow:auto; font-size:.8rem; }}
  </style>
</head>
<body {attr_string(body)}>
<main>
  <h1>state()</h1>
  <p class="muted">Day-1: <code>n = st.session("n", 0)</code> · <code>n.add(1)</code> ·
  <code>button("+", **st.bind(add))</code></p>
  <div class="row">
    {st.paint("badge", wrap=False)}
    {demo_button(ch, "Add", add)}
    {demo_button(ch, "Reset", reset)}
  </div>
  {st.paint("cart", wrap=False)}
  <p class="muted" style="margin-top:2rem">Many rows:</p>
  <pre>row = st.namespace("line", line_id)
qty = row.session("qty", 0)
@row.region
def view(ctx):
    return f"{{qty()}}"</pre>
</main>
</body>
</html>"""
