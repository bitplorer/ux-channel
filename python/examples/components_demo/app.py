"""
Plug-and-play Channel Components demo (ChannelComponent widgets; no ux-dom name clash).


  uvicorn examples.components_demo.app:app --reload --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel
from ux_channel.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)
from ux_channel.components import (
    Badge,
    Counter,
    Field,
    Flash,
    Form,
    ListView,
    Tabs,
)

app = FastAPI(title="uxchannel components")
ch = Channel.boot(app, secret="dev-secret-key-32chars-minimum!!!!")

flash = Flash(ch, uid="App:flash").install()
counter = Counter(ch, name="Qty", uid="Qty:root", min_value=0, max_value=20).install()
badge = Badge(ch, uid="Cart:badge", label="Items").install()
tabs = Tabs(
    ch,
    uid="Demo:tabs",
    panels={
        "widgets": "<p>Counters, badges, flashes — morph in place.</p>",
        "forms": "<p>Validated forms re-render with field errors.</p>",
        "lists": "<p>Search + pagination without full page reload.</p>",
    },
    labels={"widgets": "Widgets", "forms": "Forms", "lists": "Lists"},
).install()

ITEMS = [f"Product {i}" for i in range(1, 31)]


def load_items(q: str, page: int, per_page: int):
    filtered = [x for x in ITEMS if q.lower() in x.lower()] if q else ITEMS
    start = (page - 1) * per_page
    return filtered[start : start + per_page], len(filtered)


lst = ListView(
    ch,
    name="Shop",
    uid="Shop:list",
    loader=load_items,
    row=lambda it: f'<li style="padding:.35rem 0;border-bottom:1px solid #e2e8f0">{it}</li>',
    per_page=5,
).install()


def validate_contact(values: dict):
    err = {}
    if "@" not in values.get("email", ""):
        err["email"] = ["Enter a valid email"]
    if len(values.get("message", "")) < 5:
        err["message"] = ["Min 5 characters"]
    return err


def on_contact(values: dict):
    return flash.show(f"Thanks {values.get('email')}", level="success")


contact = Form(
    ch,
    name="Contact",
    uid="Contact:root",
    fields=[
        Field("email", "Email", type="email", required=True),
        Field("message", "Message", type="text", required=True),
    ],
    validate=validate_contact,
    on_submit=on_contact,
    submit_label="Send",
).install()


@ch.action("Demo.sync_badge")
def sync_badge(n: int = 0):
    # example: multi-component update from one action
    return ch.patch(
        {
            "Cart:badge": badge.render(count=n, label="Items"),
            "Qty:root": counter.render(n=n),
        },
        notice=f"Synced to {n}",
    )


@app.get("/", response_class=HTMLResponse)
def index():
    body = f"""
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; color: #0f172a; }}
  h1 {{ font-size: 1.35rem; }}
  section {{ margin: 1.5rem 0; padding: 1rem; border: 1px solid #e2e8f0; border-radius: 12px; }}
  h2 {{ font-size: 1rem; margin: 0 0 .75rem; color: #334155; }}
  code {{ background: #f1f5f9; padding: .1rem .3rem; border-radius: 4px; }}
</style>
<h1>Channel Components</h1>
<p>Drop-in regions: <code>Counter</code>, <code>Flash</code>, <code>Form</code>,
<code>ListView</code>, <code>Tabs</code>, <code>Badge</code>.</p>
{flash.render()}
<section>
  <h2>Tabs</h2>
  {tabs.render(active="widgets")}
</section>
<section>
  <h2>Counter + Badge</h2>
  {counter.render(n=0)}
  <div style="margin-top:.75rem">{badge.render(count=0, label="Items")}</div>
  <p style="margin-top:.75rem">{demo_button(ch, "Sync badge to 3", "Demo.sync_badge", trust={{"n": 3}})}</p>
</section>
<section>
  <h2>Contact form</h2>
  {contact.render()}
</section>
<section>
  <h2>Product list</h2>
  {lst.render(q="", page=1, items=ITEMS[:5], total=len(ITEMS))}
</section>
"""
    return demo_page(ch, body, title="Components demo", dev=True, inspector=True)
