"""
Pulse Desk × ux-dom — day-1 composition pattern.

Ownership (do not blur)
-----------------------
* **ux-dom** — Document shell, components, layout, tags
* **ux-channel** — boot, @region/@on (or Region), control, scripts, body attrs, webrtc

Run::

    cd uxchannel && PYTHONPATH=src:. uvicorn examples.pulse_ux_dom.app:app \\
        --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from fastapi import FastAPI

from ux_dom import Component, Document
from ux_dom.dom import button, div, form, h1, header, input_, main, nav, p, raw, span

from ux_channel import Channel, ChannelConfig
from ux_channel.paint.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)
from ux_channel.paint.response import HTMLResponse

app = FastAPI(title="Pulse × ux-dom", version="0.1.0")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="pulse-ux_dom-demo-secret-key-32ch!",
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
        webrtc_enabled=True,
    ),
)

ROOM = "pulse"


# ── channel: state + regions + actions ─────────────────────────────────────


@ch.region
def pulse_badge(ctx):
    n = int(ch.draft.get("pulses", 0) or 0)
    label = "pulse" if n == 1 else "pulses"
    # Return a fragment string OR build with ux-dom and str()/__render__
    return str(
        span(
            raw(f"<em>{n}</em>"),
            f" {label}",
            className="badge",
        )
    )


@ch.region
def activity_feed(ctx):
    items = ch.draft.get("feed") or []
    if not items:
        return str(p("No activity yet — hit Pulse.", className="feed empty"))
    lis = "".join(f"<li>{_esc(x)}</li>" for x in list(items)[-8:][::-1])
    return f'<ul class="feed">{lis}</ul>'


def _esc(s: object) -> str:
    import html as H

    return H.escape(str(s), quote=True)


@ch.on(refresh=[pulse_badge, activity_feed], idempotent=False)
def pulse(note: str = ""):
    n = int(ch.draft.get("pulses", 0) or 0) + 1
    ch.draft.set("pulses", n)
    feed = list(ch.draft.get("feed") or [])
    feed.append(f"#{n} · {(note or 'Pulse').strip()[:80]}")
    ch.draft.set("feed", feed[-20:])
    return ch.done(notice=f"Pulse #{n}")


@ch.on(refresh=[pulse_badge, activity_feed], idempotent=False)
def reset_desk():
    ch.draft.set("pulses", 0)
    ch.draft.set("feed", [])
    return ch.done(notice="Desk cleared")


# ── ux-dom components (markup only + channel attrs) ─────────────────────────


class DeskPage(Component):
    """ux-dom owns structure; channel owns signed behaviour."""

    def render(self, *args, **kwargs):
        # Freeform note → form + empty-args cap (Intent.form merge)
        form_attrs = ch.control(pulse).as_ux_dom()  # data-channel-action + cap on form
        # Prefer form protocol: control attrs on <form>, submit button plain
        return main(
            h1("Live desk"),
            p(
                "ux-dom components + channel regions/actions. ",
                "No React — morph ops from the server.",
                className="lead",
            ),
            div(
                div(
                    raw("<h2>Pulse counter</h2>"),
                    raw(ch.html(pulse_badge)),  # SSR region wrapper (data-channel-id)
                    form(
                        div(
                            input_(
                                type="text",
                                name="note",
                                placeholder="Optional note",
                                maxlength="80",
                                autocomplete="off",
                            ),
                            button("Pulse", type="submit"),
                            button(
                                "Reset",
                                type="button",
                                className="ghost",
                                **ch.control(reset_desk).as_ux_dom(),
                            ),
                            className="row",
                        ),
                        **form_attrs,
                        className="pulse-form",
                    ),
                    className="card",
                ),
                div(
                    raw("<h2>Activity</h2>"),
                    raw(ch.html(activity_feed)),
                    className="card",
                ),
                className="grid",
            ),
            className="shell-main",
        )


class Shell(Component):
    def render(self, *, active: str = "desk", body: Component | None = None):
        return div(
            nav(
                span(raw("<i></i> Pulse × ux-dom"), className="logo"),
                div(
                    raw(
                        f'<a class="{"on" if active == "desk" else ""}" href="/">Desk</a>'
                        f'<a class="{"on" if active == "call" else ""}" href="/call">Call</a>'
                    ),
                    className="nav-links",
                ),
            ),
            body or "",
            className="shell",
        )


# Document: scripts in head (channel), page body (ux-dom)
_STYLE = raw(
    """<style>
:root { --bg:#07080c; --panel:#10121a; --line:#1e2330; --text:#e8eaf0;
  --muted:#8b93a7; --accent:#6ee7b7; --font:system-ui,sans-serif; }
body { margin:0; font-family:var(--font); background:var(--bg); color:var(--text); }
.shell { max-width:52rem; margin:0 auto; padding:1.25rem; }
nav { display:flex; gap:.75rem; align-items:center; border-bottom:1px solid var(--line);
  padding-bottom:.75rem; margin-bottom:1.25rem; }
.logo { font-weight:700; } .nav-links { margin-left:auto; display:flex; gap:.5rem; }
.nav-links a { color:var(--muted); text-decoration:none; padding:.35rem .7rem; border-radius:999px; }
.nav-links a.on { color:var(--text); background:var(--panel); }
.grid { display:grid; gap:1rem; grid-template-columns:1.1fr .9fr; }
@media(max-width:720px){ .grid { grid-template-columns:1fr; } }
.card { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:1rem; }
.badge em { font-size:2.2rem; color:var(--accent); font-style:normal; font-weight:700; }
.row { display:flex; flex-wrap:wrap; gap:.5rem; margin-top:1rem; }
button { font:inherit; border:0; border-radius:10px; padding:.55rem 1rem;
  background:var(--accent); color:#042f1e; font-weight:600; cursor:pointer; }
button.ghost { background:transparent; color:var(--muted); border:1px solid var(--line); }
input { font:inherit; flex:1; min-width:8rem; padding:.55rem .75rem; border-radius:10px;
  border:1px solid var(--line); background:#0c0e14; color:var(--text); }
.feed { list-style:none; margin:0; padding:0; font-size:.85rem; color:var(--muted); }
.feed li { padding:.4rem 0; border-bottom:1px solid var(--line); }
.lead { color:var(--muted); }
</style>"""
)

document = Document(
    head=[
        raw(str(demo_scripts(ch, inspector=False))),  # ux-channel.js + webrtc
        _STYLE,
    ],
    body=[],
)


def render_page(*, active: str, body: Component, webrtc: str | bool = False) -> str:
    tree = document(
        Shell(active=active, body=body),
        title="Pulse × ux-dom",
    )
    html = tree.__render__() if hasattr(tree, "__render__") else str(tree)
    # Channel body attrs: endpoint (+ optional WebRTC room)
    attrs = attr_string(ch.body_attrs(webrtc=webrtc)) if webrtc else attr_string(ch.body_attrs())
    if "data-channel-endpoint" not in html:
        html = html.replace("<body", f"<body {attrs}", 1)
    elif webrtc and "data-channel-webrtc" not in html:
        html = html.replace("<body", f"<body {attrs}", 1)
    return html


@app.get("/health")
def health():
    return {"ok": True, "app": "pulse_ux_dom", "webrtc": ch.webrtc.diagnose()}


@app.get("/", response_class=HTMLResponse)
def desk():
    return HTMLResponse(render_page(active="desk", body=DeskPage()))


@app.get("/call", response_class=HTMLResponse)
def call():
    """Call page: ux-dom shell + same WebRTC boot pattern as pulse_desk."""
    rtc = ch.webrtc.path
    call_body = main(
        h1("Call room"),
        p(f"Signaling {rtc} — open two tabs.", className="lead"),
        raw(
            f"""
<div class="row">
  <button type="button" id="cam">Start camera</button>
  <button type="button" class="ghost" id="leave">Leave</button>
</div>
<div id="log" style="min-height:6rem;border:1px solid var(--line);border-radius:12px;padding:.75rem;margin-top:1rem;font-size:.85rem;color:var(--muted)"></div>
<script>
(function(){{
  const log = (t) => {{ const el=document.getElementById("log"); el.textContent += t+"\\n"; }};
  let room=null;
  async function join(){{
    room = await UxWebRTC.join({{ room: {ROOM!r}, rtcPath: {rtc!r},
      onMessage:(f,d)=>log("msg "+JSON.stringify(d)),
      onPeer:(id,st)=>log("peer "+id.slice(0,6)+" "+st),
      onError:(e)=>log("err "+JSON.stringify(e)) }});
    log("joined");
  }}
  document.getElementById("cam").onclick = async () => {{
    if(room) try {{ await room.startMedia({{audio:true,video:true}}); log("cam"); }} catch(e){{ log(e); }}
  }};
  document.getElementById("leave").onclick = async () => {{ if(room) await room.leave(); room=null; log("left"); }};
  function boot(n){{ if(window.UxWebRTC) return join(); if(n>100) return log("no UxWebRTC"); setTimeout(()=>boot(n+1),30); }}
  boot(0);
}})();
</script>
"""
        ),
        className="shell-main",
    )
    return HTMLResponse(render_page(active="call", body=call_body, webrtc=ROOM))
