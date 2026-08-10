"""
WebRTC mesh — data chat + optional audio/video.

Open two browser tabs (https or localhost). Use "Start camera" for A/V.

    uvicorn examples.webrtc_mesh.app:app --host 0.0.0.0 --port 8099
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig
from ux_channel.paint.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)

app = FastAPI(title="uxchannel WebRTC mesh + A/V")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
        webrtc_enabled=True,
    ),
)

PAGE = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>WebRTC · data + A/V · ux-channel</title>
  {demo_scripts(ch, inspector=False)}
  <style>
    :root {{ font-family: system-ui, sans-serif; color: #f4f4f5; background: #0a0a0b; }}
    body {{ max-width: 48rem; margin: 1.5rem auto; padding: 0 1rem; }}
    .meta {{ color: #a1a1aa; font-size: 13px; margin: .35rem 0 1rem; }}
    .videos {{ display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin-bottom: 1rem; }}
    @media (max-width: 560px) {{ .videos {{ grid-template-columns: 1fr; }} }}
    .tile {{ background: #121214; border: 1px solid #27272a; border-radius: 12px; overflow: hidden; }}
    .tile label {{ display: block; font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
                   color: #71717a; padding: .4rem .65rem; border-bottom: 1px solid #27272a; }}
    video {{ width: 100%; aspect-ratio: 4/3; object-fit: cover; background: #000; vertical-align: middle; }}
    #remotes {{ display: flex; flex-wrap: wrap; gap: .75rem; }}
    #remotes .tile {{ flex: 1 1 12rem; min-width: 10rem; }}
    #log {{ border: 1px solid #27272a; border-radius: 12px; min-height: 8rem; max-height: 14rem;
            overflow: auto; padding: .75rem; background: #121214; white-space: pre-wrap; font-size: 13px; }}
    .row {{ display: flex; flex-wrap: wrap; gap: .5rem; margin: .75rem 0; }}
    button, input {{ font: inherit; }}
    button {{ padding: .5rem .9rem; border: 0; border-radius: 8px; background: #f4f4f5; color: #0a0a0b; cursor: pointer; }}
    button.ghost {{ background: transparent; border: 1px solid #3f3f46; color: #a1a1aa; }}
    input {{ flex: 1; min-width: 8rem; padding: .5rem .7rem; border-radius: 8px; border: 1px solid #3f3f46;
             background: #1a1a1e; color: inherit; }}
  </style>
</head>
<body {attr_string(ch.body_attrs(webrtc="demo"))}>
  <h1>WebRTC mesh</h1>
  <p class="meta">Signaling <code>{ch.webrtc.path}</code> · data channel <code>uid</code> · media tracks for A/V</p>

  <div class="videos">
    <div class="tile">
      <label>Local</label>
      <video id="local" autoplay playsinline muted></video>
    </div>
    <div class="tile">
      <label>Remotes</label>
      <div id="remotes"></div>
    </div>
  </div>

  <div class="row">
    <button type="button" id="btn-av">Start camera + mic</button>
    <button type="button" id="btn-audio" class="ghost">Audio only</button>
    <button type="button" id="btn-mute-a" class="ghost">Mute mic</button>
    <button type="button" id="btn-mute-v" class="ghost">Mute cam</button>
    <button type="button" id="btn-stop" class="ghost">Stop media</button>
  </div>

  <div id="log">connecting…</div>
  <form id="f" class="row">
    <input id="msg" placeholder="Text over data channel…" autocomplete="off"/>
    <button>Send</button>
  </form>

  <script>
    const log = (t) => {{
      const el = document.getElementById('log');
      el.textContent += t + '\\n';
      el.scrollTop = el.scrollHeight;
    }};
    const remotes = document.getElementById('remotes');
    const tiles = {{}};
    let room;
    let mutedA = false, mutedV = false;

    function ensureRemoteVideo(peerId, stream) {{
      let tile = tiles[peerId];
      if (!tile) {{
        tile = document.createElement('div');
        tile.className = 'tile';
        tile.innerHTML = '<label></label><video autoplay playsinline></video>';
        tile.querySelector('label').textContent = peerId.slice(0, 10);
        remotes.appendChild(tile);
        tiles[peerId] = tile;
      }}
      tile.querySelector('video').srcObject = stream;
    }}

    (async () => {{
      room = await UxWebRTC.join({{
        room: 'demo',
        rtcPath: '{ch.webrtc.path}',
        onRoster: (peers) => {{
          /* keep log of roster size */
        }},
        onMessage: (from, data) => log('← ' + from.slice(0, 8) + ': ' + JSON.stringify(data)),
        onPeer: (id, st) => log('· ' + id.slice(0, 8) + ' ' + st),
        onLocalStream: (stream) => {{
          document.getElementById('local').srcObject = stream;
          log('local media on');
        }},
        onTrack: (peerId, stream) => {{
          ensureRemoteVideo(peerId, stream);
          log('remote track from ' + peerId.slice(0, 8));
        }},
        onError: (e) => log('! ' + JSON.stringify(e)),
      }});
      log('joined as ' + room.peer + ' (data channel ready; start media when you want)');
    }})();

    document.getElementById('btn-av').onclick = async () => {{
      try {{ await room.startMedia({{ audio: true, video: true }}); }}
      catch (e) {{ log('media error: ' + e); }}
    }};
    document.getElementById('btn-audio').onclick = async () => {{
      try {{ await room.startMedia({{ audio: true, video: false }}); }}
      catch (e) {{ log('media error: ' + e); }}
    }};
    document.getElementById('btn-mute-a').onclick = () => {{
      mutedA = !mutedA;
      room.muteAudio(mutedA);
      log(mutedA ? 'mic muted' : 'mic on');
    }};
    document.getElementById('btn-mute-v').onclick = () => {{
      mutedV = !mutedV;
      room.muteVideo(mutedV);
      log(mutedV ? 'cam muted' : 'cam on');
    }};
    document.getElementById('btn-stop').onclick = async () => {{
      await room.stopMedia();
      document.getElementById('local').srcObject = null;
      log('media stopped');
    }};
    document.getElementById('f').onsubmit = (e) => {{
      e.preventDefault();
      const v = document.getElementById('msg').value;
      if (!v || !room) return;
      room.send({{ text: v, t: Date.now() }});
      log('→ ' + v);
      document.getElementById('msg').value = '';
    }};
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    return HTMLResponse(PAGE)


@app.get("/health")
def health():
    return {"ok": True, "webrtc": ch.webrtc.diagnose(), "planes": ["signaling", "data", "media"]}
