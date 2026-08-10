"""
WebRTC ready demo — **app owns UI**, channel owns plugin/signaling.

  PYTHONPATH=src uvicorn examples.webrtc_ready.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig
from ux_channel.paint.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)

SECRET = os.environ.get(
    "UX_CHANNEL_SECRET", "webrtc-ready-dev-secret-key-32ch!!"
)
if os.environ.get("CHANNEL_ENV", "development") == "production":
    cfg = ChannelConfig.production(SECRET)
else:
    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
        webrtc_enabled=True,
    )

app = FastAPI(title="WebRTC Ready", version="0.1.0")
ch = Channel.boot(app, config=cfg)


@app.get("/health")
def health():
    return {"ok": True, "webrtc": ch.webrtc.diagnose()}


@app.get("/plugin.json")
def plugin_json(request: Request):
    room = request.query_params.get("room") or "lobby"
    return ch.webrtc.plugin(room, sub=request.query_params.get("user") or "").as_dict()


def _host_page(p, *, title: str) -> str:
    """Example-local markup only — not part of ux-channel."""
    client = json.dumps(p.client)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
{script_tags(p)}
<style>
  body{{margin:0;font-family:system-ui,sans-serif;background:#0a0a0c;color:#e8eaf0}}
  main{{max-width:40rem;margin:auto;padding:1.25rem}}
  video{{width:100%;background:#000;border-radius:12px;margin:.5rem 0}}
  .row{{display:flex;flex-wrap:wrap;gap:.5rem;margin:.75rem 0}}
  button,input{{font:inherit;padding:.5rem .75rem;border-radius:8px;border:0}}
  button{{background:#6ee7b7;color:#042f1e;font-weight:600;cursor:pointer}}
  input{{flex:1;background:#12141c;color:inherit;border:1px solid #1e2330}}
  #log{{white-space:pre-wrap;border:1px solid #1e2330;border-radius:12px;
    padding:.75rem;min-height:5rem;background:#12141c;font-size:12px;color:#8b93a7}}
</style>
</head>
<body {attr_string(p)}>
<main>
  <h1>{title}</h1>
  <p>Plugin placement only · room <code>{p.room}</code> · <code>{p.path}</code></p>
  <video id="local" autoplay playsinline muted></video>
  <div id="remotes"></div>
  <div class="row">
    <button type="button" id="cam">Start camera</button>
    <button type="button" id="mic">Audio only</button>
    <button type="button" id="leave">Leave</button>
  </div>
  <pre id="log">…</pre>
  <form id="chat" class="row">
    <input id="msg" placeholder="Data-channel message" autocomplete="off"/>
    <button type="submit">Send</button>
  </form>
</main>
<script>
(function(){{
  var OPTS = {client};
  var logEl = document.getElementById("log");
  var log = function(t){{ logEl.textContent += t + "\\n"; }};
  var room = null;
  function boot(n){{
    if (!window.UxWebRTC) {{
      if (n > 120) return log("UxWebRTC missing");
      return setTimeout(function(){{ boot(n+1); }}, 25);
    }}
    UxWebRTC.join(Object.assign({{}}, OPTS, {{
      onMessage: function(f,d){{ log("<- " + JSON.stringify(d)); }},
      onPeer: function(id,st){{ log(id.slice(0,8)+" "+st); }},
      onLocalStream: function(s){{ document.getElementById("local").srcObject = s; }},
      onTrack: function(id, stream){{
        var v = document.getElementById("r-"+id);
        if (!v) {{
          v = document.createElement("video");
          v.id = "r-"+id; v.autoplay = true; v.playsInline = true;
          document.getElementById("remotes").appendChild(v);
        }}
        v.srcObject = stream;
      }},
      onError: function(e){{ log("! "+JSON.stringify(e)); }},
    }})).then(function(r){{ room = r; log("joined "+r.peer); }});
  }}
  boot(0);
  document.getElementById("cam").onclick = function(){{
    if (room) room.startMedia({{audio:true,video:true}});
  }};
  document.getElementById("mic").onclick = function(){{
    if (room) room.startMedia({{audio:true,video:false}});
  }};
  document.getElementById("leave").onclick = function(){{
    if (room) room.leave(); room = null;
  }};
  document.getElementById("chat").onsubmit = function(e){{
    e.preventDefault();
    var v = document.getElementById("msg").value;
    if (room && v) {{ room.send({{text:v}}); log("-> "+v); document.getElementById("msg").value=""; }}
  }};
}})();
</script>
</body></html>
"""


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    room = request.query_params.get("room") or "lobby"
    p = ch.webrtc.plugin(room)
    return HTMLResponse(_host_page(p, title="Ready room"))
