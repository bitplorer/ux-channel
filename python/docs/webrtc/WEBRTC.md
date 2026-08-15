<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# WebRTC (P2P) — data + audio/video

uxchannel ships a **WebRTC plane** out of the box:

| Plane | Transport | Role |
|-------|-----------|------|
| **Signaling** | HTTP `GET/POST {path}/rtc` + **WS** `{path}/rtc/ws` | Roster + SDP/ICE (trickle) |
| **Data** | `RTCDataChannel` `"uid"` | Chat / state sync |
| **Audio / video** | **MediaStream tracks** on same `RTCPeerConnection` | Mic / camera |
| **Ops push** | SSE / WebSocket | Server→client morph (separate) |

**A/V and data bytes never hit your server** — only SDP/ICE signaling does.

---

Signaling protocol deep-dive: [WEBRTC_SIGNALING.md](WEBRTC_SIGNALING.md) (offer/answer/ice/ice-done, HTTP + **WebSocket**, tickets, TURN).

## Enable (default)

```python
ch = Channel.boot(app, config=ChannelConfig.development(
    secret="…", allow_memory_stores=True,
    # webrtc_enabled=True  ← default
))
```

Disable: `webrtc_enabled=False`.

---

## Client — data only

```js
const room = await UxWebRTC.join({
  room: "lobby",
  rtcPath: "/ux-channel/rtc",
  onMessage: (peerId, data) => console.log(peerId, data),
});
room.send({ hello: true });
```

## Client — audio / video

```js
const room = await UxWebRTC.join({
  room: "call",
  rtcPath: "/ux-channel/rtc",
  media: { audio: true, video: true },  // or "audio" | "video" | "av" | true
  onLocalStream: (stream) => {
    document.getElementById("local").srcObject = stream;
  },
  onTrack: (peerId, stream, track) => {
    // one <video> per peer, or reuse
    let el = document.getElementById("remote-" + peerId);
    if (!el) {
      el = document.createElement("video");
      el.id = "remote-" + peerId;
      el.autoplay = true;
      el.playsInline = true;
      document.getElementById("remotes").appendChild(el);
    }
    el.srcObject = stream;
  },
});

// later:
await room.startMedia({ audio: true, video: false }); // audio-only
room.muteAudio(true);
room.muteVideo(true);
await room.stopMedia();
```

### After join (lazy media)

```js
const room = await UxWebRTC.join({ room: "call" });
// user clicks "Join with camera"
await room.startMedia({ audio: true, video: true });
```

---

## Python / HTML wiring

```python
str(ch.scripts())  # includes ux-webrtc.js when enabled

# body attrs
ch.body_attr_string(
    webrtc="call-room",
    webrtc_auto=True,
    webrtc_media="av",   # "audio" | "video" | "av"
)
# → data-channel-webrtc-rtc data-channel-webrtc-room data-channel-webrtc-auto data-channel-webrtc-media

ch.webrtc.body_attrs(room="lobby", auto=True, media="audio")
```

---

## HTTP signaling API

Unchanged:

* `GET {path}/rtc?room=&peer=&name=&since=`
* `POST {path}/rtc` with `op: signal|leave`

Media is negotiated inside SDP payloads (`kind: offer|answer`); ICE is `kind: ice`.

---

## Config

| Flag | Default | Meaning |
|------|---------|---------|
| `webrtc_enabled` | `True` | Mount `/rtc` + ship JS |
| `webrtc_max_peers` | `8` | Room soft cap (mesh O(N²)) |
| `webrtc_peer_ttl_s` | `30` | Drop silent peers |
| `webrtc_signal_ttl_s` | `60` | Drop old SDP/ICE |
| `webrtc_require_origin` | `False` | Origin check on `/rtc` |

Optional client: pass `iceServers` into `UxWebRTC.join` (e.g. your TURN).

```js
UxWebRTC.join({
  iceServers: [
    { urls: "stun:stun.l.google.com:19302" },
    { urls: "turn:turn.example.com", username: "u", credential: "p" },
  ],
  media: { audio: true, video: true },
});
```

---

## Security / product fit

* **Co-op / calls among consenting peers** — no server A/V authority.
* ICE may expose IPs — use TURN in production for NAT + privacy policy.
* Secure context required (`https` or `localhost`) for `getUserMedia`.
* Trusted business state still uses `@ch.on` + caps, not the mesh.

---

## API summary (`UidRtcRoom`)

| Method | Purpose |
|--------|---------|
| `send` / `sendTo` | Data channel |
| `startMedia({audio, video})` | `getUserMedia` + publish tracks |
| `muteAudio` / `muteVideo` | Enable/disable tracks |
| `stopMedia` | Stop capture + remove senders |
| `getRemoteStream(peerId)` | Last remote `MediaStream` |
| `leave` | Stop media + close peers + signal leave |

Events / callbacks: `onMessage`, `onPeer`, `onRoster`, `onTrack`, `onLocalStream`, `onError`.

DOM events (auto-join): `ux-webrtc-message`, `ux-webrtc-peer`, `ux-webrtc-track`, `ux-webrtc-local`.

---

## Data channel upgrades (0.1+)

Label remains **`"uid"`** (one channel). Reliability and payload shape are opt-in.

### Queue until open

Early `send` / `sendTo` no longer drops when the DC is still connecting — messages
are queued (max 64 per peer, oldest dropped) and flushed on `datachannel-open`.

```js
room.send({ hello: true }); // OK even before onPeer(..., "datachannel-open")
```

### Binary

```js
const room = await UxWebRTC.join({
  room: "lobby",
  rtcPath: "/ux-channel/rtc",
  onMessage: (id, data) => { /* JSON / string */ },
  onBinary: (id, buf) => { /* ArrayBuffer */ },
});

const bytes = new TextEncoder().encode("snapshot");
room.sendBinary(bytes.buffer);
room.sendBinaryTo(peerId, bytes);
```

If `onBinary` is omitted, binary arrives as `onMessage(id, { __binary: true, data })`.

### Reliability modes (`dcMode`)

| `dcMode` | SCTP options | Use |
|----------|--------------|-----|
| `"reliable"` (default) | `ordered: true` | Chat, state sync |
| `"unreliable"` / `"game"` | `ordered: false`, `maxRetransmits: 0` | High-frequency positions |
| `"partial"` | `ordered: true`, `maxRetransmits: 3` | Soft real-time |

```js
await UxWebRTC.join({
  room: "arena",
  rtcPath: "/ux-channel/rtc",
  dcMode: "unreliable",
  onMessage: (id, state) => applyRemote(state),
});
```

Both peers should use the **same** `dcMode` (initiator creates the channel).

### Helpers

```js
room.isDataOpen(peerId); // true → send without waiting on queue
```

### Non-goals

* Multiple named channels (`uid.chat` / `uid.sync`) — multiplex with `{ type }` in JSON first.
* Server-side visibility of DC payloads — still P2P only.

### Typed multiplex (`pub` / `on`) — still one DataChannel

Logical topics over the single `"uid"` channel (no extra SCTP streams):

```js
const room = await UxWebRTC.join({ room: "lobby", rtcPath: "/ux-channel/rtc" });

room.on("chat", (from, msg) => console.log(from, msg.text));
room.on("cursor", (from, pos) => draw(from, pos));

room.pub("chat", { text: "hi" });
room.pubTo(peerId, "cursor", { x: 10, y: 20 });
```

Envelope on the wire: `{ __uid: 1, t: "chat", d: { text: "hi" } }`.  
`onMessage` still receives the full envelope (and topic handlers run).

### Backpressure

If `bufferedAmount` exceeds `maxBufferedAmount` (default 256 KiB), sends stay queued
until `bufferedamountlow`. Override:

```js
UxWebRTC.join({ room: "r", rtcPath: "/ux-channel/rtc", maxBufferedAmount: 128 * 1024 });
```

### Chunked files

```js
room = await UxWebRTC.join({
  room: "lobby",
  rtcPath: "/ux-channel/rtc",
  onFile: (from, file) => {
    // file: { id, name, type, size, buffer }
    download(file.name, file.buffer);
  },
});

await room.sendFile(fileInput.files[0]); // Blob
await room.sendFileTo(peerId, arrayBuffer, { name: "snap.bin" });
```

16 KiB binary frames with a tiny header; JSON `__file` announce first.
