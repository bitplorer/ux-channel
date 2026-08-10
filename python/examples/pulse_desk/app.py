"""
Pulse Desk — production-shaped demo for uxchannel 0.1.

Day-1 API only (see Channel.mental_model()):

    boot → @region → @on → control → scripts → draft/done → webrtc

Run::

    uvicorn examples.pulse_desk.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import html as html_lib

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig
from ux_channel.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)

app = FastAPI(
    title="Pulse Desk",
    description="uxchannel day-1 demo: regions + WebRTC",
    version="0.1.0",
)

ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="pulse-desk-demo-secret-key-32ch!!",
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
        webrtc_enabled=True,
    ),
)

ROOM = "pulse"


def _esc(s: str) -> str:
    return html_lib.escape(s, quote=True)


# ── regions ────────────────────────────────────────────────────────────────


@ch.region
def pulse_badge(ctx):
    # Wrapper from ch.html() is data-channel-id="pulse.badge" — keep inner free of uid ids
    n = int(ch.draft.get("pulses", 0) or 0)
    label = "pulse" if n == 1 else "pulses"
    return f'<span class="badge"><em>{n}</em> {label}</span>'


@ch.region
def activity_feed(ctx):
    items = ch.draft.get("feed") or []
    if not isinstance(items, list):
        items = []
    if not items:
        return (
            '<div class="feed empty">'
            "<p>No activity yet — hit <strong>Pulse</strong>.</p></div>"
        )
    lis = "".join(f"<li>{_esc(str(x))}</li>" for x in items[-8:][::-1])
    return f'<ul class="feed">{lis}</ul>'


# ── actions ────────────────────────────────────────────────────────────────


@ch.on(refresh=[pulse_badge, activity_feed], idempotent=False)
def pulse(note: str = ""):
    n = int(ch.draft.get("pulses", 0) or 0) + 1
    ch.draft.set("pulses", n)
    feed = list(ch.draft.get("feed") or [])
    msg = (note or "").strip() or "Pulse"
    feed.append(f"#{n} · {msg[:80]}")
    ch.draft.set("feed", feed[-20:])
    return ch.done(notice=f"Pulse #{n}")


@ch.on(refresh=[pulse_badge, activity_feed], idempotent=False)
def reset_desk():
    ch.draft.set("pulses", 0)
    ch.draft.set("feed", [])
    return ch.done(notice="Desk cleared")


# ── chrome ─────────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg: #07080c;
  --panel: #10121a;
  --line: #1e2330;
  --text: #e8eaf0;
  --muted: #8b93a7;
  --accent: #6ee7b7;
  --accent-dim: #34d39955;
  --warn: #fbbf24;
  --radius: 14px;
  --font: "DM Sans", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, monospace;
}
* { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; }
body {
  font-family: var(--font);
  background:
    radial-gradient(1200px 600px at 10% -10%, #1a2744 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #0f3d32 0%, transparent 50%),
    var(--bg);
  color: var(--text);
  line-height: 1.5;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.shell { max-width: 52rem; margin: 0 auto; padding: 1.25rem 1.1rem 3rem; }
nav {
  display: flex; align-items: center; gap: .75rem; flex-wrap: wrap;
  margin-bottom: 1.5rem; padding-bottom: .9rem; border-bottom: 1px solid var(--line);
}
.logo {
  font-weight: 700; letter-spacing: -.02em; font-size: 1.05rem;
  display: flex; align-items: center; gap: .45rem;
}
.logo i {
  width: .65rem; height: .65rem; border-radius: 50%;
  background: var(--accent); box-shadow: 0 0 12px var(--accent);
  display: inline-block;
}
.nav-links { margin-left: auto; display: flex; gap: .35rem; }
.nav-links a {
  color: var(--muted); padding: .35rem .7rem; border-radius: 999px; font-size: .9rem;
}
.nav-links a.on, .nav-links a:hover {
  color: var(--text); background: var(--panel); text-decoration: none;
}
h1 { font-size: 1.65rem; letter-spacing: -.03em; margin: 0 0 .35rem; font-weight: 700; }
.lead { color: var(--muted); margin: 0 0 1.25rem; max-width: 36rem; font-size: .98rem; }
.grid {
  display: grid; gap: 1rem;
  grid-template-columns: 1.1fr .9fr;
}
@media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }
.card {
  background: linear-gradient(165deg, #141824 0%, var(--panel) 100%);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.1rem 1.15rem 1.2rem;
  box-shadow: 0 12px 40px #00000055;
}
.card h2 {
  margin: 0 0 .75rem; font-size: .72rem; font-weight: 600;
  letter-spacing: .12em; text-transform: uppercase; color: var(--muted);
}
.badge {
  display: inline-flex; align-items: baseline; gap: .4rem;
  font-size: 1.35rem; font-weight: 600; letter-spacing: -.02em;
}
.badge em {
  font-style: normal; font-size: 2.4rem; font-weight: 700;
  color: var(--accent); font-variant-numeric: tabular-nums;
  text-shadow: 0 0 24px var(--accent-dim);
}
.row { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; align-items: center; }
button, .btn {
  font: inherit; cursor: pointer; border: 0; border-radius: 10px;
  padding: .55rem 1rem; background: var(--accent); color: #042f1e; font-weight: 600;
}
button:hover { filter: brightness(1.06); }
button.ghost {
  background: transparent; color: var(--muted);
  border: 1px solid var(--line);
}
button.ghost:hover { color: var(--text); }
button.uid-busy, button[aria-busy="true"] { opacity: .65; pointer-events: none; }
input[type=text] {
  font: inherit; flex: 1; min-width: 8rem;
  padding: .55rem .75rem; border-radius: 10px;
  border: 1px solid var(--line); background: #0c0e14; color: var(--text);
}
.feed {
  list-style: none; margin: 0; padding: 0;
  font-family: var(--mono); font-size: .8rem; color: var(--muted);
}
.feed li { padding: .45rem 0; border-bottom: 1px solid var(--line); }
.feed.empty p { margin: 0; color: var(--muted); font-size: .9rem; }
.meta {
  margin-top: 1.5rem; font-size: .78rem; color: var(--muted);
  font-family: var(--mono);
}
.meta code { color: var(--warn); }
.hint {
  margin-top: 1rem; padding: .75rem .9rem; border-radius: 10px;
  background: #0c1220; border: 1px solid var(--line);
  font-size: .88rem; color: var(--muted);
}
.videos {
  display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin-bottom: 1rem;
}
@media (max-width: 560px) { .videos { grid-template-columns: 1fr; } }
.tile {
  background: #0a0c12; border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
}
.tile label {
  display: block; font-size: .65rem; letter-spacing: .1em; text-transform: uppercase;
  color: var(--muted); padding: .4rem .65rem; border-bottom: 1px solid var(--line);
}
video {
  width: 100%; aspect-ratio: 4/3; object-fit: cover; background: #000; vertical-align: middle;
}
#remotes { display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1rem; }
#remotes .tile { flex: 1 1 11rem; min-width: 9rem; }
#log {
  border: 1px solid var(--line); border-radius: 12px; min-height: 7rem; max-height: 12rem;
  overflow: auto; padding: .75rem; background: #0a0c12;
  white-space: pre-wrap; font-size: .8rem; font-family: var(--mono); color: var(--muted);
}
#ux-channel-toasts {
  position: fixed; right: 1rem; bottom: 1rem; z-index: 9999;
  display: flex; flex-direction: column; gap: .4rem; max-width: 18rem;
}
#ux-channel-toasts .uid-toast {
  padding: .55rem .75rem; border-radius: 10px;
  background: #1a2030; border: 1px solid var(--line); color: var(--text);
  font-size: .85rem; box-shadow: 0 8px 24px #0008;
}
"""


def _nav(active: str) -> str:
    def link(href: str, label: str, key: str) -> str:
        on = " on" if active == key else ""
        return f'<a class="{on.strip()}" href="{href}">{label}</a>'

    return f"""
<nav>
  <div class="logo"><i></i> Pulse Desk</div>
  <div class="nav-links">
    {link("/", "Desk", "desk")}
    {link("/call", "Call", "call")}
  </div>
</nav>
"""


def _layout(*, title: str, active: str, body: str, body_attrs: str = "") -> str:
    fonts = (
        '<link rel="preconnect" href="https://fonts.googleapis.com"/>'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>'
        '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700'
        '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title} · Pulse Desk</title>
  {fonts}
  {demo_scripts(ch, inspector=False)}
  <style>{_CSS}</style>
</head>
<body {body_attrs}>
  <div class="shell">
    {_nav(active)}
    {body}
  </div>
</body>
</html>
"""


@app.get("/health")
def health():
    return {
        "ok": True,
        "app": "pulse_desk",
        "version": "0.1.0",
        "webrtc": ch.webrtc.diagnose(),
        "pulses": ch.draft.get("pulses", 0),
    }


@app.get("/", response_class=HTMLResponse)
def desk():
    """
    Desk bugs fixed:
    * freeform note via <form data-channel-action> + submit (Intent.form merge)
    * reset stays a signed button control
    * no nested data-channel-id fighting morph targets
    """
    form_open = ch.form(pulse, class_name="pulse-form")
    reset_attrs = ch.control(reset_desk).as_dict()
    attr_s = " ".join(f'{k}="{_esc(str(v))}"' for k, v in reset_attrs.items())

    body = f"""
    <h1>Live desk</h1>
    <p class="lead">
      Server-driven UI: Python owns state and HTML fragments.
      The browser applies morph ops — no React tree.
    </p>
    <div class="grid">
      <section class="card">
        <h2>Pulse counter</h2>
        {ch.html(pulse_badge)}
        {form_open}
          <div class="row">
            <input type="text" name="note" placeholder="Optional note" maxlength="80"
                   autocomplete="off"/>
            <button type="submit">Pulse</button>
            <button type="button" class="ghost" {attr_s}>Reset</button>
          </div>
        </form>
        <p class="hint">
          Freeform fields use a <strong>signed form</strong> (empty-args cap;
          <code>note</code> arrives in <code>Intent.form</code>).
        </p>
      </section>
      <section class="card">
        <h2>Activity</h2>
        {ch.html(activity_feed)}
      </section>
    </div>
    <p class="meta">
      action <code>{ch.path}/action</code>
      · rtc <code>{ch.webrtc.path}</code>
      · day-1 <code>Channel.mental_model()</code>
    </p>
    """
    return HTMLResponse(
        _layout(
            title="Desk",
            active="desk",
            body=body,
            body_attrs=attr_string(ch.body_attrs()),
        )
    )


@app.get("/call", response_class=HTMLResponse)
def call():
    """
    Call bugs fixed:
    * wait for deferred ux-webrtc.js before UxWebRTC.join
    * body webrtc room attrs for tooling; explicit join for control
    """
    ticket = ""
    try:
        if getattr(ch.config, "webrtc_require_ticket", False):
            ticket = ch.webrtc.sign_ticket(ROOM, sub="demo")
    except Exception:
        ticket = ""

    body_attrs = attr_string(ch.body_attrs(webrtc=ROOM))
    if ticket and "data-channel-webrtc-ticket" not in body_attrs:
        body_attrs += f' data-channel-webrtc-ticket="{_esc(ticket)}"'

    rtc = ch.webrtc.path
    body = f"""
    <h1>Call room</h1>
    <p class="lead">
      P2P mesh: signaling at <code>{rtc}</code>.
      Media/data bytes never hit the server.
    </p>
    <div class="videos">
      <div class="tile">
        <label>You</label>
        <video id="local" autoplay playsinline muted></video>
      </div>
      <div class="tile">
        <label>Room · {ROOM}</label>
        <div id="remotes"></div>
      </div>
    </div>
    <div class="row">
      <button type="button" id="cam">Start camera</button>
      <button type="button" class="ghost" id="mute">Mute</button>
      <button type="button" class="ghost" id="leave">Leave</button>
    </div>
    <div class="row">
      <input id="msg" type="text" placeholder="Data-channel message" maxlength="200"/>
      <button type="button" id="send">Send</button>
    </div>
    <div id="log"></div>
    <p class="hint">Open in <strong>two tabs</strong>. Camera needs <strong>https</strong> or <strong>localhost</strong> and permission. Watch the log below for errors.</p>
    <p class="meta">ws <code>{ch.webrtc.ws_path}</code> · plane <code>ch.webrtc</code></p>
    <script>
    (function () {{
      const logEl = document.getElementById("log");
      const log = (t) => {{ logEl.textContent += t + "\\n"; logEl.scrollTop = logEl.scrollHeight; }};
      let room = null;
      let muted = false;
      const rtcPath = {rtc!r};
      const roomName = {ROOM!r};
      const ticket = {ticket!r};

      function tile(peerId, stream) {{
        let el = document.getElementById("v-" + peerId);
        if (!el) {{
          const wrap = document.createElement("div");
          wrap.className = "tile";
          wrap.innerHTML = "<label>peer " + peerId.slice(0, 6) + "</label>";
          el = document.createElement("video");
          el.id = "v-" + peerId;
          el.autoplay = true;
          el.playsInline = true;
          wrap.appendChild(el);
          document.getElementById("remotes").appendChild(wrap);
        }}
        el.srcObject = stream;
      }}

      const camBtn = document.getElementById("cam");
      const muteBtn = document.getElementById("mute");
      const leaveBtn = document.getElementById("leave");
      const sendBtn = document.getElementById("send");
      const localVid = document.getElementById("local");

      function setBusy(on) {{
        camBtn.disabled = !!on;
        camBtn.textContent = on ? "Starting…" : "Start camera";
      }}

      async function attachLocal(stream) {{
        if (!localVid || !stream) return;
        if (localVid.srcObject !== stream) localVid.srcObject = stream;
        localVid.muted = true;
        localVid.playsInline = true;
        localVid.setAttribute("playsinline", "");
        localVid.setAttribute("autoplay", "");
        try {{
          await localVid.play();
        }} catch (e) {{
          // AbortError if a second load races — retry once after metadata
          await new Promise(function (res) {{
            if (localVid.readyState >= 1) return res();
            localVid.onloadedmetadata = function () {{ res(); }};
            setTimeout(res, 400);
          }});
          try {{ await localVid.play(); }}
          catch (e2) {{ log("local play: " + (e2 && e2.message ? e2.message : e2)); }}
        }}
      }}

      async function join() {{
        try {{
          room = await UxWebRTC.join({{
            room: roomName,
            rtcPath: rtcPath,
            ticket: ticket || undefined,
            onMessage: (from, data) => log("← " + from.slice(0, 6) + " " + JSON.stringify(data)),
            onPeer: (id, st) => log("peer " + id.slice(0, 6) + " " + st),
            onLocalStream: (s) => {{ attachLocal(s); }},
            onTrack: (id, stream) => tile(id, stream),
            onError: (e) => log("err " + (typeof e === "string" ? e : JSON.stringify(e))),
            onRoster: (peers) => log("roster " + peers.length),
          }});
          log("joined " + roomName + " as " + (room.peer || "?").toString().slice(0, 8));
          camBtn.disabled = false;
          if (!window.isSecureContext) {{
            log("⚠ Not a secure context — camera may be blocked. Use https or localhost.");
          }}
        }} catch (e) {{
          log("join failed: " + e);
        }}
      }}

      camBtn.disabled = true;
      camBtn.onclick = async () => {{
        if (!room) {{ log("not joined yet — wait a moment"); return; }}
        setBusy(true);
        try {{
          // onLocalStream → attachLocal (do not call attachLocal again — play() race)
          const stream = await room.startMedia({{ audio: true, video: true }});
          const v = stream.getVideoTracks().length;
          const a = stream.getAudioTracks().length;
          log("camera on (video tracks=" + v + ", audio tracks=" + a + ")");
        }} catch (e) {{
          log("media error: " + (e && e.message ? e.message : e));
          log("tip: allow camera/mic in the browser; needs https or localhost");
        }} finally {{
          setBusy(false);
        }}
      }};
      muteBtn.onclick = () => {{
        if (!room) return;
        muted = !muted;
        room.muteAudio(muted);
        log(muted ? "muted" : "unmuted");
      }};
      leaveBtn.onclick = async () => {{
        if (room) await room.leave();
        room = null;
        if (localVid) localVid.srcObject = null;
        camBtn.disabled = true;
        log("left");
      }};
      sendBtn.onclick = () => {{
        if (!room) return;
        const v = document.getElementById("msg").value || "";
        const n = room.send({{ text: v, t: Date.now() }});
        log("→ (" + n + " peers) " + v);
        document.getElementById("msg").value = "";
      }};

      // demo_scripts(ch, ) uses defer — wait for UxWebRTC
      function bootWhenReady(tries) {{
        tries = tries || 0;
        if (window.UxWebRTC) {{ join(); return; }}
        if (tries > 100) {{ log("UxWebRTC missing — check demo_scripts(ch, ) / network"); return; }}
        setTimeout(function () {{ bootWhenReady(tries + 1); }}, 30);
      }}
      if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", function () {{ bootWhenReady(0); }});
      }} else {{
        bootWhenReady(0);
      }}
    }})();
    </script>
    """
    return HTMLResponse(
        _layout(title="Call", active="call", body=body, body_attrs=body_attrs)
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "examples.pulse_desk.app:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
    )
