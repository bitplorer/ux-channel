"""
Named recipes — copy-paste application patterns (low cognitive load).

Philosophy
----------
One problem → one recipe name. No framework UI. Prefer ``ch.control`` + host markup.
"""

from __future__ import annotations

from typing import Any

__all__ = ["RECIPE_NAMES", "recipe", "recipe_text", "decision_tree"]

RECIPE_NAMES = (
    "counter",
    "form",
    "media-mesh",
    "media-sfu",
    "ux-dom-control",
    "bridge-npm",
    "chart-widget",
    "production",
)


def recipe_text(name: str) -> str:
    """Return a complete, teachable snippet for *name*."""
    key = (name or "").strip().lower().replace("_", "-")
    try:
        return _RECIPES[key]
    except KeyError as exc:
        raise KeyError(
            f"unknown recipe {name!r}; choose from {list(RECIPE_NAMES)}"
        ) from exc


def recipe(name: str) -> dict[str, Any]:
    """Structured recipe: name, summary, code, avoid."""
    text = recipe_text(name)
    meta = _META.get(name.strip().lower().replace("_", "-"), {})
    return {
        "name": name,
        "summary": meta.get("summary", ""),
        "avoid": meta.get("avoid", ()),
        "code": text,
    }


def decision_tree() -> str:
    """Single-screen: which API for which job."""
    return (
        "What do you need?\n"
        "-----------------\n"
        "Interactive HTML form / button click\n"
        "  → @ch.on + ch.control(...)  [recipe: form | ux-dom-control]\n"
        "Live region without full page reload\n"
        "  → @ch.region + refresh=[…]   [recipe: counter]\n"
        "1:1 or tiny group A/V (no SFU ops)\n"
        "  → ch.media.plugin(room, mode='mesh')  [recipe: media-mesh]\n"
        "Group calls / production multiparty\n"
        "  → LIVEKIT_* + ch.media.plugin(mode='sfu')  [recipe: media-sfu]\n"
        "Scaffold a project\n"
        "  → uxchannel create-app myapp [-t media|live|minimal]\n"
        "Deploy checklist\n"
        "  → recipe production + uxchannel check --env production\n"
        "\n"
        "Do NOT use for product UI\n"
        "  Channel HTML façade  (removed — ux_channel.render.kit only)\n"
        "  ch.webrtc.page / call chrome  (removed — host owns UI)\n"
    )


_META = {
    "counter": {
        "summary": "Region morph counter — core SDUI loop",
        "avoid": ("Channel HTML façade in product", "full page reloads"),
    },
    "form": {
        "summary": "Signed form post with empty-args cap",
        "avoid": ("unsigned action posts",),
    },
    "media-mesh": {
        "summary": "Mesh placement bag + host <video>",
        "avoid": ("embedding TURN secrets in HTML", "library call chrome"),
    },
    "media-sfu": {
        "summary": "LiveKit token bag via ch.media",
        "avoid": ("open /sfu/token without tickets", "vendoring livekit-client in channel"),
    },
    "ux-dom-control": {
        "summary": "ux-dom button with ch.control attrs",
        "avoid": ("ch.button", "hand-rolled data-uid without control()"),
    },
    "production": {
        "summary": "Fail-closed config checklist",
        "avoid": ("allow_memory_stores multi-worker", "require_cap=False"),
    },
    "bridge-npm": {
        "summary": "Any npm widget via string bridge ops (not FFI)",
        "avoid": ("expecting Python to call JS by handle", "bridge.mount for LiveKit"),
    },
    "chart-widget": {
        "summary": "Chart.js without Chart.js — Chart(ch, id).set_values",
        "avoid": ("raw bridge.call setType unless needed",),
    },
}


_RECIPES: dict[str, str] = {
    "chart-widget": """# Chart — bind channel once, call for islands
from ux_channel.bridges import ChartBridge

charts = ChartBridge(ch)   # factory
rev = charts(
    "revenue",
    labels=["Mon", "Tue", "Wed"],
    values=[12, 19, 8],
    kind="bar",
    title="Weekly",
)

@ch.on
def reshuffle():
    return rev.commit(values=[4, 9, 14])   # ch.done under the hood

@ch.on
def as_line():
    return rev.commit_kind("line")

# ux-dom: host from rev.mount_spec().attrs
""",
    "bridge-npm": """# Any npm package — automated preset (preferred)

# 1) Generate preset (adapter + contract + Python façade)
uxchannel bridge catalog
uxchannel bridge preset chartjs --out bridges
# or scaffold: uxchannel create-app myapp --bridge chartjs

# 2) Python (importable package)
from bridges.chartjs import ChartJsBridge

widgets = ChartJsBridge(ch)
w = widgets("c1", props={"type": "bar", "data": data})

@ch.on
def show():
    return w.commit_mount()
@ch.on
def refresh():
    return w.commit(data=new_data)

# 3) ux-dom: host from w.mount_spec().attrs  + load adapter JS
# 4) Power escape: ch.bridge.call(...) still works
""",
    "counter": '''\
from fastapi import FastAPI
from ux_channel import Channel, ChannelConfig

app = FastAPI()
ch = Channel.boot(app, config=ChannelConfig.development(
    secret="dev-secret-key-32chars-minimum!!!!",
    allow_memory_stores=True,
))

@ch.region
def badge(ctx):
    return f"<b>{ch.draft.get("n", 0)}</b>"

@ch.on(refresh=[badge], idempotent=False)
def add():
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)

# Host UI (ux-dom / HTML): place ch.scripts() + button with ch.control(add)
# attrs = ch.control(add).as_dict()
''',
    "form": '''\
@ch.on(idempotent=True)
def save(ctx, title: str = ""):
    ch.draft.set("title", title)
    return ch.done(notice="saved")

# open form:  ch.form(save)  → demo only
# product:    <form {ch.control(save).attr_string}> … </form>
''',
    "media-mesh": '''\
p = ch.media.plugin("lobby", sub=user_id, mode="mesh")
# head:  p.scripts_html
# body:  p.attr_string
# join:  UxWebRTC.join(p.client)   # host attaches MediaStreams
''',
    "media-sfu": '''\
# env: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
p = ch.media.plugin(room_id, sub=user_id, mode="sfu", cdn=False)
# place p.scripts_html (or bundle livekit-client yourself)
# p.client = { url, token, room, identity, provider }
# Prefer server-side plugin after YOUR auth — not open HTTP mint.
''',
    "ux-dom-control": '''\
# ux-dom (or any Python HTML DSL)
from ux_dom import button  # illustrative

button("Add", **ch.control(add, trust_sku=sku).as_dict())
# or underscore style:
button("Add", **ch.control(add, trust_sku=sku).as_ux_dom())
''',
    "production": '''\
from ux_channel import ChannelConfig

cfg = ChannelConfig.production(
    secret=os.environ["UX_CHANNEL_SECRET"],
    allowed_origins=("https://app.example.com",),
    redis_url=os.environ["REDIS_URL"],
    webrtc_enabled=True,
    webrtc_require_ticket=True,
    webrtc_require_origin=True,
    # sfu_provider="livekit", sfu_url=..., sfu_api_key=..., sfu_api_secret=...
)
# uxchannel check --env production --secret "$UX_CHANNEL_SECRET"
# TURN for mesh NATs; LiveKit for multiparty A/V
''',
}
