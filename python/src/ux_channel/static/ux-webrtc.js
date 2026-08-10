/**
 * ux-webrtc.js — WebRTC mesh client for uxchannel (browser only).
 *
 * =============================================================================
 * Wire contract (must match Python `ux_channel.webrtc`)
 * =============================================================================
 * Transports
 *   1. WebSocket  {rtcPath}/ws  (e.g. /ux-channel/rtc/ws) — trickle ICE
 *   2. HTTP poll  {rtcPath}        — join snapshot + fallback
 *   3. HTTP POST  {rtcPath}        — signal | leave
 *   4. HTTP GET   {rtcPath}/ice    — ticketed STUN+TURN (iceUrl)
 *
 * Signal kinds (application ferry for JSEP / ICE):
 *   offer | answer | ice | ice-done
 *
 *   offer/answer payload → RTCSessionDescriptionInit { type, sdp }  (sdp has v=)
 *   ice payload          → RTCIceCandidateInit object
 *   ice-done payload     → null  → addIceCandidate(null) end-of-candidates
 *
 * Client → server:  { op: "signal"|"leave"|"ping", room, from, to?, kind?, payload? }
 * Server → client:  { type: "hello"|"roster"|"signal"|"peer_left"|"pong"|"error", ... }
 * HTTP poll body:   { ok, peers, signals: [{id,from,kind,payload}], ... }
 *
 * ICE placement (same rule as ch.webrtc.ice):
 *   iceServers  = public STUN only (html)
 *   iceUrl      = GET …/rtc/ice with ticket → short-lived TURN (live)
 *   Never put TURN passwords in data-channel-webrtc-ice.
 *
 * Media plane (NOT server):
 *   RTCDataChannel label "uid", MediaStream tracks via getUserMedia.
 *   Secure context required for A/V (https or localhost).
 *
 * See docs/STANDARDS.md · docs/WEBRTC_SIGNALING.md
 * =============================================================================
 */
(function (global) {
  "use strict";

  var DEFAULT_ICE = [{ urls: "stun:stun.l.google.com:19302" }];
  /** Keep major aligned with package / ux-channel.js */
  var WEBRTC_VERSION = "0.1.0";
  var POLL_MS = 800;

  function peerId() {
    var a = new Uint8Array(9);
    crypto.getRandomValues(a);
    var s = "";
    for (var i = 0; i < a.length; i++) s += (a[i] % 36).toString(36);
    return "p_" + s;
  }

  function json(res) { return res.json(); }

  function normalizeMedia(media) {
    if (!media) return null;
    if (media === true || media === "av") return { audio: true, video: true };
    if (media === "audio") return { audio: true, video: false };
    if (media === "video") return { audio: false, video: true };
    if (typeof media === "object") {
      return {
        audio: !!media.audio,
        video: !!media.video,
        audioConstraints: media.audioConstraints || media.audio || true,
        videoConstraints: media.videoConstraints || media.video || true,
      };
    }
    return null;
  }

  function parseIceAttr(raw) {
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (_) { return null; }
  }

  /** RTCDataChannelInit from join opts.dcMode */
  function dataChannelInit(opts) {
    var mode = (opts && (opts.dcMode || opts.dataChannelMode)) || "reliable";
    if (mode === "unreliable" || mode === "lossy" || mode === "game") {
      // Best-effort: unordered, no retransmit (high-frequency state)
      return { ordered: false, maxRetransmits: 0 };
    }
    if (mode === "partial" || mode === "partial-reliable") {
      return { ordered: true, maxRetransmits: 3 };
    }
    // reliable (default) — TCP-like ordered delivery
    return { ordered: true };
  }

  function isBinaryPayload(data) {
    if (data == null) return false;
    if (typeof ArrayBuffer !== "undefined" && data instanceof ArrayBuffer) return true;
    if (typeof Uint8Array !== "undefined" && data instanceof Uint8Array) return true;
    if (typeof Blob !== "undefined" && data instanceof Blob) return true;
    return false;
  }

  var DC_QUEUE_MAX = 64;
  var DC_CHUNK = 16 * 1024; // 16 KiB payload per chunk
  var DC_BUF_DEFAULT = 256 * 1024; // backpressure threshold
  var DC_MAGIC = 0x5543; // "UC" binary frame

  function hashId(s) {
    var h = 2166136261;
    s = String(s || "");
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function toArrayBuffer(data) {
    if (!data) return null;
    if (data instanceof ArrayBuffer) return data;
    if (typeof Uint8Array !== "undefined" && data instanceof Uint8Array) {
      return data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
    }
    if (typeof Blob !== "undefined" && data instanceof Blob) return null; // async path
    return null;
  }

  /** Build binary chunk frame: magic|flags|idHash|index|total|payload */
  function encodeChunkFrame(id, index, total, payloadBuf) {
    var u8 = payloadBuf instanceof Uint8Array
      ? payloadBuf
      : new Uint8Array(payloadBuf);
    var out = new ArrayBuffer(12 + u8.byteLength);
    var view = new DataView(out);
    view.setUint16(0, DC_MAGIC, false);
    view.setUint16(2, 1, false); // flags: chunk
    view.setUint32(4, hashId(id), false);
    view.setUint16(8, index, false);
    view.setUint16(10, total, false);
    new Uint8Array(out, 12).set(u8);
    return out;
  }

  function decodeChunkFrame(buf) {
    if (!buf || buf.byteLength < 12) return null;
    var view = new DataView(buf);
    if (view.getUint16(0, false) !== DC_MAGIC) return null;
    if (view.getUint16(2, false) !== 1) return null;
    return {
      idHash: view.getUint32(4, false),
      index: view.getUint16(8, false),
      total: view.getUint16(10, false),
      payload: buf.slice(12),
    };
  }

  function UidRtcRoom(opts) {
    this.opts = opts || {};
    this.rtcPath = (opts.rtcPath || "/ux-channel/rtc").replace(/\/$/, "");
    this.wsPath = opts.wsPath || (this.rtcPath + "/ws");
    this.room = opts.room || "default";
    this.peer = opts.peerId || peerId();
    this.name = opts.name || "";
    this.ticket = opts.ticket || "";
    this.since = 0;
    this.pcs = Object.create(null);
    this.dcs = Object.create(null);
    this.remoteStreams = Object.create(null);
    this.roster = [];
    this._timer = null;
    this._alive = true;
    this._makingOffer = Object.create(null);
    this._ignoreOffer = Object.create(null);
    this._ws = null;
    this._useWs = opts.preferWs !== false;
    this._wsRetries = 0;
    this._wsMaxRetries = opts.wsMaxRetries != null ? opts.wsMaxRetries : 12;
    this._reconnectTimer = null;
    this.localStream = null;
    this.iceServers = opts.iceServers || DEFAULT_ICE;
    this.iceUrl = opts.iceUrl || ""; // GET …/rtc/ice for short-lived TURN
    this.onMessage = opts.onMessage || function () {};
    this.onPeer = opts.onPeer || function () {};
    this.onRoster = opts.onRoster || function () {};
    this.onError = opts.onError || function () {};
    this.onTrack = opts.onTrack || function () {};
    this.onLocalStream = opts.onLocalStream || function () {};
    this.onBinary = opts.onBinary || null; // optional: (peerId, ArrayBuffer|Blob) =>
    this.onFile = opts.onFile || null; // optional: (peerId, {name,type,size,buffer}) =>
    this.media = normalizeMedia(opts.media);
    this.simulcast = !!opts.simulcast;
    this.iceTransportPolicy = opts.iceTransportPolicy || "all"; // "all" | "relay"
    this._dcInit = dataChannelInit(opts);
    this._dcQueues = Object.create(null); // peerId -> [{kind:'json'|'bin', payload}]
    this._dcBroadcastQ = []; // messages before any peer DC exists
    this.maxBufferedAmount = opts.maxBufferedAmount != null ? opts.maxBufferedAmount : DC_BUF_DEFAULT;
    this._topics = Object.create(null); // topic -> [fn]
    this._chunkAsm = Object.create(null); // key peerId:idHash -> { meta, parts, got }
    this._fileMeta = Object.create(null); // idHash -> meta from __file announce
  }

  UidRtcRoom.prototype._ticketQ = function () {
    return this.ticket ? "&ticket=" + encodeURIComponent(this.ticket) : "";
  };

  UidRtcRoom.prototype._pollUrl = function () {
    return (
      this.rtcPath +
      "?room=" + encodeURIComponent(this.room) +
      "&peer=" + encodeURIComponent(this.peer) +
      "&since=" + encodeURIComponent(String(this.since)) +
      (this.name ? "&name=" + encodeURIComponent(this.name) : "") +
      this._ticketQ()
    );
  };

  UidRtcRoom.prototype._headers = function () {
    var h = {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Channel": "1",
    };
    if (this.ticket) h["X-Channel-Rtc-Ticket"] = this.ticket;
    return h;
  };

  UidRtcRoom.prototype._postHttp = async function (body) {
    if (this.ticket) body.ticket = this.ticket;
    var res = await fetch(this.rtcPath, {
      method: "POST",
      credentials: "same-origin",
      headers: this._headers(),
      body: JSON.stringify(body),
    });
    if (!res.ok) this.onError({ phase: "post", status: res.status });
    return res;
  };

  UidRtcRoom.prototype._sendSignal = async function (body) {
    body.op = body.op || "signal";
    if (this._ws && this._ws.readyState === 1) {
      this._ws.send(JSON.stringify(body));
      return;
    }
    await this._postHttp(body);
  };

  UidRtcRoom.prototype._applyRoster = function (peers) {
    this.roster = peers || [];
    this.onRoster(this.roster.slice());
    var self = this;
    (this.roster || []).forEach(function (p) {
      if (p.id !== self.peer) self._ensurePeer(p.id, self.peer < p.id);
    });
    Object.keys(this.pcs).forEach(function (id) {
      var still = (self.roster || []).some(function (p) { return p.id === id; });
      if (!still) self._dropPeer(id);
    });
  };

  UidRtcRoom.prototype._ingestSignal = async function (s) {
    if (!s) return;
    if (s.id && s.id > this.since) this.since = s.id;
    await this._handleSignal(s);
  };

  UidRtcRoom.prototype._poll = async function () {
    if (!this._alive) return;
    try {
      var res = await fetch(this._pollUrl(), {
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-Channel-Rtc-Ticket": this.ticket || "" },
      });
      if (!res.ok) {
        this.onError({ phase: "poll", status: res.status });
        return;
      }
      var data = await json(res);
      this._applyRoster(data.peers || []);
      var signals = data.signals || [];
      for (var i = 0; i < signals.length; i++) await this._ingestSignal(signals[i]);
    } catch (e) {
      this.onError({ phase: "poll", error: String(e) });
    }
  };

  UidRtcRoom.prototype._connectWs = function () {
    var self = this;
    if (!this._useWs || typeof WebSocket === "undefined") return Promise.resolve(false);
    return new Promise(function (resolve) {
      try {
        var proto = location.protocol === "https:" ? "wss:" : "ws:";
        var host = location.host;
        var path =
          self.wsPath +
          "?room=" + encodeURIComponent(self.room) +
          "&peer=" + encodeURIComponent(self.peer) +
          (self.name ? "&name=" + encodeURIComponent(self.name) : "") +
          self._ticketQ();
        var url = path.indexOf("ws") === 0 ? path : proto + "//" + host + path;
        var ws = new WebSocket(url);
        var settled = false;
        var timer = setTimeout(function () {
          if (!settled) {
            settled = true;
            try { ws.close(); } catch (_) {}
            resolve(false);
          }
        }, 2500);
        ws.onopen = function () {
          self._ws = ws;
          self._wsRetries = 0;
          if (!settled) { settled = true; clearTimeout(timer); resolve(true); }
        };
        ws.onerror = function () {
          if (!settled) { settled = true; clearTimeout(timer); resolve(false); }
        };
        ws.onclose = function () {
          self._ws = null;
          if (!self._alive) return;
          // exponential backoff reconnect (P1); poll while waiting
          if (!self._timer) {
            self._timer = setInterval(function () { self._poll(); }, self.opts.pollMs || POLL_MS);
          }
          if (self._wsRetries < self._wsMaxRetries) {
            var delay = Math.min(30000, 500 * Math.pow(2, self._wsRetries));
            self._wsRetries += 1;
            self.onPeer(self.peer, "ws-reconnect-in-" + delay + "ms");
            self._reconnectTimer = setTimeout(function () {
              if (!self._alive) return;
              self._connectWs().then(function (ok) {
                if (ok) {
                  self._wsRetries = 0;
                  if (self._timer) { clearInterval(self._timer); self._timer = null; }
                  // light presence timer like start()
                  self._timer = setInterval(function () {
                    if (self._ws && self._ws.readyState === 1) {
                      self._ws.send(JSON.stringify({ op: "poll", since: self.since }));
                    } else {
                      self._poll();
                    }
                  }, Math.max(5000, (self.opts.pollMs || POLL_MS) * 6));
                }
              });
            }, delay);
          }
        };
        ws.onmessage = function (ev) {
          var msg;
          try { msg = JSON.parse(ev.data); } catch (_) { return; }
          var t = msg.type;
          if (t === "hello") {
            self._applyRoster(msg.peers || []);
            (msg.signals || []).forEach(function (s) { self._ingestSignal(s); });
          } else if (t === "roster") {
            self._applyRoster(msg.peers || []);
          } else if (t === "signal") {
            self._ingestSignal(msg);
          } else if (t === "peer_left") {
            self._applyRoster(msg.peers || []);
            if (msg.peer) self._dropPeer(msg.peer);
          } else if (t === "error") {
            self.onError({ phase: "ws", error: msg.error || "error" });
          }
        };
      } catch (e) {
        resolve(false);
      }
    });
  };

  UidRtcRoom.prototype._simulcastEncodings = function () {
    // 3-layer simulcast (RID q/h/f) — SFU-friendly; browsers ignore if unsupported
    return [
      { rid: "q", scaleResolutionDownBy: 4, maxBitrate: 150000, active: true },
      { rid: "h", scaleResolutionDownBy: 2, maxBitrate: 500000, active: true },
      { rid: "f", scaleResolutionDownBy: 1, maxBitrate: 1500000, active: true },
    ];
  };

  UidRtcRoom.prototype._addLocalTracks = function (pc) {
    if (!this.localStream) return;
    var self = this;
    this.localStream.getTracks().forEach(function (track) {
      var already = pc.getSenders().some(function (s) {
        return s.track && s.track.id === track.id;
      });
      if (already) return;
      try {
        if (
          self.simulcast &&
          track.kind === "video" &&
          typeof pc.addTransceiver === "function"
        ) {
          pc.addTransceiver(track, {
            direction: "sendrecv",
            streams: [self.localStream],
            sendEncodings: self._simulcastEncodings(),
          });
        } else {
          pc.addTrack(track, self.localStream);
        }
      } catch (e) {
        // Fallback if transceiver encodings rejected
        try { pc.addTrack(track, self.localStream); }
        catch (e2) { self.onError({ phase: "addTrack", error: String(e2) }); }
      }
    });
  };

  UidRtcRoom.prototype._ensurePeer = function (remoteId, initiator) {
    if (this.pcs[remoteId]) {
      this._addLocalTracks(this.pcs[remoteId]);
      return this.pcs[remoteId];
    }
    var pc = new RTCPeerConnection({
      iceServers: this.iceServers,
      iceTransportPolicy: this.iceTransportPolicy || "all",
    });
    this.pcs[remoteId] = pc;
    var self = this;
    var polite = this.peer > remoteId;

    pc.onicecandidate = function (ev) {
      if (!ev.candidate) {
        // end-of-candidates (trickle complete for this side)
        self._sendSignal({
          op: "signal",
          room: self.room,
          from: self.peer,
          to: remoteId,
          kind: "ice-done",
          payload: null,
        });
        return;
      }
      self._sendSignal({
        op: "signal",
        room: self.room,
        from: self.peer,
        to: remoteId,
        kind: "ice",
        payload: ev.candidate.toJSON ? ev.candidate.toJSON() : ev.candidate,
      });
    };

    pc.onconnectionstatechange = function () {
      self.onPeer(remoteId, pc.connectionState || "unknown");
    };

    pc.ontrack = function (ev) {
      var stream = (ev.streams && ev.streams[0]) || self.remoteStreams[remoteId];
      if (!stream) {
        stream = new MediaStream();
        self.remoteStreams[remoteId] = stream;
      }
      if (!stream.getTracks().some(function (t) { return t.id === ev.track.id; })) {
        stream.addTrack(ev.track);
      }
      self.remoteStreams[remoteId] = stream;
      self.onTrack(remoteId, stream, ev.track, ev);
      self.onPeer(remoteId, "track:" + ev.track.kind);
    };

    this._addLocalTracks(pc);

    if (initiator) {
      var dc = pc.createDataChannel("uid", self._dcInit || { ordered: true });
      this._bindDc(remoteId, dc);
      this._negotiate(remoteId);
    } else {
      pc.ondatachannel = function (ev) { self._bindDc(remoteId, ev.channel); };
    }
    pc._uidPolite = polite;
    return pc;
  };

  UidRtcRoom.prototype._negotiate = async function (remoteId) {
    var pc = this.pcs[remoteId];
    if (!pc || !this._alive) return;
    try {
      this._makingOffer[remoteId] = true;
      var offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await this._sendSignal({
        op: "signal",
        room: this.room,
        from: this.peer,
        to: remoteId,
        kind: "offer",
        payload: pc.localDescription,
      });
    } catch (e) {
      this.onError({ phase: "offer", peer: remoteId, error: String(e) });
    } finally {
      this._makingOffer[remoteId] = false;
    }
  };


  UidRtcRoom.prototype._handleSignal = async function (s) {
    var from = s.from;
    if (!from || from === this.peer) return;
    var polite = this.peer > from;
    var pc = this._ensurePeer(from, false);
    try {
      if (s.kind === "offer") {
        var offerCollision =
          this._makingOffer[from] ||
          (pc.signalingState && pc.signalingState !== "stable");
        this._ignoreOffer[from] = !polite && offerCollision;
        if (this._ignoreOffer[from]) return;
        await pc.setRemoteDescription(s.payload);
        this._addLocalTracks(pc);
        var answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        await this._sendSignal({
          op: "signal",
          room: this.room,
          from: this.peer,
          to: from,
          kind: "answer",
          payload: pc.localDescription,
        });
      } else if (s.kind === "answer") {
        if (this._ignoreOffer[from]) return;
        try { await pc.setRemoteDescription(s.payload); } catch (_) {}
      } else if (s.kind === "ice") {
        try { if (s.payload) await pc.addIceCandidate(s.payload); } catch (_) {}
      } else if (s.kind === "ice-done") {
        try { await pc.addIceCandidate(null); } catch (_) {}
        this.onPeer(from, "ice-done");
      }
    } catch (e) {
      this.onError({ phase: "signal", kind: s.kind, error: String(e) });
    }
  };

  UidRtcRoom.prototype._dropPeer = function (id) {
    try { if (this.dcs[id]) this.dcs[id].close(); } catch (_) {}
    try { if (this.pcs[id]) this.pcs[id].close(); } catch (_) {}
    delete this.dcs[id];
    delete this.pcs[id];
    delete this.remoteStreams[id];
    delete this._makingOffer[id];
    delete this._ignoreOffer[id];
    delete this._dcQueues[id];
    var self = this;
    Object.keys(this._chunkAsm || {}).forEach(function (k) {
      if (k.indexOf(id + ":") === 0) delete self._chunkAsm[k];
    });
    this.onPeer(id, "left");
  };

  UidRtcRoom.prototype._bindDc = function (remoteId, dc) {
    this.dcs[remoteId] = dc;
    var self = this;
    try { dc.binaryType = "arraybuffer"; } catch (_) {}

    dc.onmessage = function (ev) {
      self._onDcMessage(remoteId, ev.data);
    };

    dc.onopen = function () {
      self.onPeer(remoteId, "datachannel-open");
      self._flushDcQueue(remoteId);
      self._flushBroadcastQueue();
    };
    dc.onclose = function () {
      self.onPeer(remoteId, "datachannel-close");
    };
    dc.onerror = function (ev) {
      self.onError({ phase: "datachannel", peer: remoteId, error: String(ev && ev.error || "dc-error") });
    };
    // Backpressure: flush queue when buffer drains
    try {
      dc.bufferedAmountLowThreshold = Math.min(self.maxBufferedAmount, 64 * 1024);
      dc.onbufferedamountlow = function () {
        self._flushDcQueue(remoteId);
        self._flushBroadcastQueue();
      };
    } catch (_) {}

    // Already open (rare race)
    if (dc.readyState === "open") {
      self._flushDcQueue(remoteId);
      self._flushBroadcastQueue();
    }
  };

  UidRtcRoom.prototype._enqueueDc = function (peerId, item) {
    if (!this._dcQueues[peerId]) this._dcQueues[peerId] = [];
    var q = this._dcQueues[peerId];
    if (q.length >= DC_QUEUE_MAX) q.shift(); // drop oldest
    q.push(item);
  };

  UidRtcRoom.prototype._rawSend = function (dc, item) {
    if (!dc || dc.readyState !== "open") return false;
    // Backpressure: leave item in queue if SCTP buffer is full
    if (this.maxBufferedAmount > 0 && typeof dc.bufferedAmount === "number") {
      if (dc.bufferedAmount > this.maxBufferedAmount) return false;
    }
    try {
      if (item.kind === "bin") {
        var payload = item.payload;
        if (typeof Uint8Array !== "undefined" && payload instanceof Uint8Array) {
          // send underlying buffer slice if needed
          if (payload.byteOffset === 0 && payload.byteLength === payload.buffer.byteLength) {
            dc.send(payload.buffer);
          } else {
            dc.send(payload.buffer.slice(payload.byteOffset, payload.byteOffset + payload.byteLength));
          }
        } else {
          dc.send(payload);
        }
      } else {
        var data = item.payload;
        dc.send(typeof data === "string" ? data : JSON.stringify(data));
      }
      return true;
    } catch (e) {
      this.onError({ phase: "dc-send", error: String(e) });
      return false;
    }
  };

  UidRtcRoom.prototype._flushDcQueue = function (peerId) {
    var dc = this.dcs[peerId];
    var q = this._dcQueues[peerId];
    if (!dc || !q || !q.length) return;
    while (q.length) {
      if (!this._rawSend(dc, q[0])) break;
      q.shift();
    }
  };

  UidRtcRoom.prototype._flushBroadcastQueue = function () {
    if (!this._dcBroadcastQ.length) return;
    var self = this;
    var left = [];
    this._dcBroadcastQ.forEach(function (item) {
      var n = 0;
      Object.keys(self.dcs).forEach(function (id) {
        if (self._rawSend(self.dcs[id], item)) n++;
        else self._enqueueDc(id, item);
      });
      if (n === 0 && Object.keys(self.dcs).length === 0) left.push(item);
    });
    this._dcBroadcastQ = left;
  };

  /**
   * Send JSON/string to one peer. Queues until datachannel-open.
   * @returns {boolean} true if sent or queued
   */
  UidRtcRoom.prototype.sendTo = function (peerId, data) {
    if (isBinaryPayload(data)) return this.sendBinaryTo(peerId, data);
    var item = { kind: "json", payload: data };
    var dc = this.dcs[peerId];
    if (dc && dc.readyState === "open") return this._rawSend(dc, item);
    this._enqueueDc(peerId, item);
    return true; // queued
  };

  /**
   * Broadcast JSON/string to all peers (open now or queue).
   * @returns {number} peers that accepted immediately (queued peers not counted)
   */
  UidRtcRoom.prototype.send = function (data) {
    if (isBinaryPayload(data)) return this.sendBinary(data);
    var self = this;
    var item = { kind: "json", payload: data };
    var n = 0;
    var ids = Object.keys(this.dcs);
    if (!ids.length) {
      if (this._dcBroadcastQ.length >= DC_QUEUE_MAX) this._dcBroadcastQ.shift();
      this._dcBroadcastQ.push(item);
      return 0;
    }
    ids.forEach(function (id) {
      var dc = self.dcs[id];
      if (dc && dc.readyState === "open") {
        if (self._rawSend(dc, item)) n++;
      } else {
        self._enqueueDc(id, item);
      }
    });
    return n;
  };

  /** Binary unicast (ArrayBuffer | Uint8Array | Blob). Queues until open. */
  UidRtcRoom.prototype.sendBinaryTo = function (peerId, buf) {
    var item = { kind: "bin", payload: buf };
    var dc = this.dcs[peerId];
    if (dc && dc.readyState === "open") return this._rawSend(dc, item);
    this._enqueueDc(peerId, item);
    return true;
  };

  /** Binary broadcast. @returns immediate send count */
  UidRtcRoom.prototype.sendBinary = function (buf) {
    var self = this;
    var item = { kind: "bin", payload: buf };
    var n = 0;
    var ids = Object.keys(this.dcs);
    if (!ids.length) {
      if (this._dcBroadcastQ.length >= DC_QUEUE_MAX) this._dcBroadcastQ.shift();
      this._dcBroadcastQ.push(item);
      return 0;
    }
    ids.forEach(function (id) {
      var dc = self.dcs[id];
      if (dc && dc.readyState === "open") {
        if (self._rawSend(dc, item)) n++;
      } else {
        self._enqueueDc(id, item);
      }
    });
    return n;
  };

  /** True if DC to peer is open (safe for latency-sensitive sends without queue). */
  UidRtcRoom.prototype.isDataOpen = function (peerId) {
    var dc = this.dcs[peerId];
    return !!(dc && dc.readyState === "open");
  };

  // --- Typed multiplex on single "uid" channel (no extra DataChannels) -----

  /**
   * Subscribe to a logical topic. Messages from pub(topic, data) hit these handlers.
   * Also delivered to onMessage as { t, d } envelope.
   * @returns {function} unsubscribe
   */
  UidRtcRoom.prototype.on = function (topic, fn) {
    topic = String(topic || "");
    if (!this._topics[topic]) this._topics[topic] = [];
    this._topics[topic].push(fn);
    var self = this;
    return function unsubscribe() {
      var list = self._topics[topic] || [];
      self._topics[topic] = list.filter(function (f) { return f !== fn; });
    };
  };

  /** Publish JSON to a topic (all peers). Envelope: { __uid:1, t, d } */
  UidRtcRoom.prototype.pub = function (topic, data) {
    return this.send({ __uid: 1, t: String(topic || ""), d: data });
  };

  /** Publish JSON to one peer on a topic */
  UidRtcRoom.prototype.pubTo = function (peerId, topic, data) {
    return this.sendTo(peerId, { __uid: 1, t: String(topic || ""), d: data });
  };

  UidRtcRoom.prototype._dispatchTopic = function (peerId, envelope) {
    var topic = envelope && envelope.t;
    var list = topic != null ? this._topics[topic] : null;
    if (list && list.length) {
      for (var i = 0; i < list.length; i++) {
        try { list[i](peerId, envelope.d, envelope); } catch (e) {
          this.onError({ phase: "topic", topic: topic, error: String(e) });
        }
      }
    }
  };

  UidRtcRoom.prototype._onDcMessage = function (remoteId, raw) {
    // Binary chunk frames or raw binary
    if (isBinaryPayload(raw)) {
      var buf = raw instanceof ArrayBuffer ? raw : toArrayBuffer(raw);
      if (buf) {
        var frame = decodeChunkFrame(buf);
        if (frame) {
          this._acceptChunk(remoteId, frame);
          return;
        }
      }
      if (typeof this.onBinary === "function") {
        this.onBinary(remoteId, raw);
      } else {
        this.onMessage(remoteId, { __binary: true, data: raw });
      }
      return;
    }
    var data = raw;
    if (typeof data === "string") {
      try { data = JSON.parse(data); } catch (_) {}
    }
    // File announce
    if (data && data.__uid === 1 && data.t === "__file" && data.d) {
      var meta = data.d;
      this._fileMeta[hashId(meta.id)] = meta;
      this._chunkAsm[remoteId + ":" + hashId(meta.id)] = {
        meta: meta,
        parts: new Array(meta.n || 0),
        got: 0,
      };
      return;
    }
    // Typed envelope
    if (data && data.__uid === 1 && typeof data.t === "string") {
      this._dispatchTopic(remoteId, data);
      this.onMessage(remoteId, data);
      return;
    }
    this.onMessage(remoteId, data);
  };

  UidRtcRoom.prototype._acceptChunk = function (remoteId, frame) {
    var key = remoteId + ":" + frame.idHash;
    var asm = this._chunkAsm[key];
    if (!asm) {
      // late/unknown — stash minimal
      asm = {
        meta: this._fileMeta[frame.idHash] || { id: String(frame.idHash), n: frame.total },
        parts: new Array(frame.total),
        got: 0,
      };
      this._chunkAsm[key] = asm;
    }
    if (asm.parts[frame.index]) return; // dup
    asm.parts[frame.index] = new Uint8Array(frame.payload);
    asm.got++;
    if (asm.got < (asm.meta.n || frame.total)) return;
    // reassemble
    var total = 0;
    for (var i = 0; i < asm.parts.length; i++) {
      if (!asm.parts[i]) return; // gap
      total += asm.parts[i].byteLength;
    }
    var out = new Uint8Array(total);
    var off = 0;
    for (var j = 0; j < asm.parts.length; j++) {
      out.set(asm.parts[j], off);
      off += asm.parts[j].byteLength;
    }
    delete this._chunkAsm[key];
    var file = {
      id: asm.meta.id,
      name: asm.meta.name || "file",
      type: asm.meta.type || "application/octet-stream",
      size: asm.meta.size || out.byteLength,
      buffer: out.buffer,
    };
    if (typeof this.onFile === "function") {
      this.onFile(remoteId, file);
    } else if (typeof this.onBinary === "function") {
      this.onBinary(remoteId, file.buffer);
    } else {
      this.onMessage(remoteId, { __file: true, from: remoteId, file: file });
    }
  };

  /**
   * Send large binary in 16KiB frames (with optional file meta).
   * @param {ArrayBuffer|Uint8Array|Blob} data
   * @param {{name?:string, type?:string, id?:string}} [meta]
   */
  UidRtcRoom.prototype.sendFile = async function (data, meta) {
    return this._sendFileTo(null, data, meta);
  };

  UidRtcRoom.prototype.sendFileTo = async function (peerId, data, meta) {
    return this._sendFileTo(peerId, data, meta);
  };

  UidRtcRoom.prototype._sendFileTo = async function (peerId, data, meta) {
    meta = meta || {};
    var buf = data;
    if (typeof Blob !== "undefined" && data instanceof Blob) {
      buf = await data.arrayBuffer();
      if (!meta.name && data.name) meta.name = data.name;
      if (!meta.type && data.type) meta.type = data.type;
    }
    var ab = toArrayBuffer(buf);
    if (!ab) throw new Error("sendFile: need ArrayBuffer, Uint8Array, or Blob");
    var id = meta.id || ("f_" + peerId_gen());
    var u8 = new Uint8Array(ab);
    var n = Math.max(1, Math.ceil(u8.byteLength / DC_CHUNK) || 1);
    var announce = {
      __uid: 1,
      t: "__file",
      d: {
        id: id,
        name: meta.name || "file",
        type: meta.type || "application/octet-stream",
        size: u8.byteLength,
        n: n,
      },
    };
    if (peerId) this.sendTo(peerId, announce);
    else this.send(announce);
    for (var i = 0; i < n; i++) {
      var slice = u8.subarray(i * DC_CHUNK, Math.min(u8.byteLength, (i + 1) * DC_CHUNK));
      var frame = encodeChunkFrame(id, i, n, slice);
      if (peerId) this.sendBinaryTo(peerId, frame);
      else this.sendBinary(frame);
    }
    return { id: id, chunks: n, size: u8.byteLength };
  };

  function peerId_gen() {
    var a = new Uint8Array(6);
    if (typeof crypto !== "undefined" && crypto.getRandomValues) crypto.getRandomValues(a);
    var s = "";
    for (var i = 0; i < a.length; i++) s += (a[i] % 36).toString(36);
    return s;
  }

  UidRtcRoom.prototype.peers = function () { return this.roster.slice(); };
  UidRtcRoom.prototype.getRemoteStream = function (peerId) {
    return this.remoteStreams[peerId] || null;
  };

  UidRtcRoom.prototype.startMedia = async function (media) {
    var spec = normalizeMedia(media != null ? media : this.media || { audio: true, video: true });
    if (!spec || (!spec.audio && !spec.video)) throw new Error("startMedia: need audio and/or video");
    // Secure context: localhost / https only (browsers block getUserMedia on plain http)
    if (typeof window !== "undefined" && window.isSecureContext === false) {
      throw new Error(
        "Camera needs a secure context (https or localhost). This page is not secure."
      );
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("getUserMedia not available (secure context or browser permission)");
    }
    var constraints = {
      audio: spec.audio
        ? (spec.audioConstraints && typeof spec.audioConstraints === "object"
            ? spec.audioConstraints
            : true)
        : false,
      video: spec.video
        ? (spec.videoConstraints && typeof spec.videoConstraints === "object"
            ? spec.videoConstraints
            : { facingMode: "user" })
        : false,
    };
    var stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (err) {
      // Fallback: video-only if mic denied, or audio-only if camera denied
      var name = (err && err.name) || "";
      if (constraints.audio && constraints.video) {
        try {
          stream = await navigator.mediaDevices.getUserMedia({
            audio: false,
            video: constraints.video,
          });
        } catch (e2) {
          try {
            stream = await navigator.mediaDevices.getUserMedia({
              audio: constraints.audio,
              video: false,
            });
          } catch (e3) {
            var msg = (err && (err.message || err.name)) || String(err);
            throw new Error("getUserMedia failed: " + msg);
          }
        }
      } else {
        var msg2 = (err && (err.message || err.name)) || String(err);
        throw new Error("getUserMedia failed: " + msg2);
      }
    }
    // Prefer the new stream as local (cleaner than splicing tracks)
    if (this.localStream && this.localStream !== stream) {
      try {
        this.localStream.getTracks().forEach(function (t) { t.stop(); });
      } catch (_) {}
    }
    this.localStream = stream;
    this.media = spec;
    this.onLocalStream(this.localStream);
    var self2 = this;
    // Always re-attach + renegotiate so remote peers receive new A/V tracks
    Object.keys(this.pcs).forEach(function (id) {
      self2._addLocalTracks(self2.pcs[id]);
      self2._negotiate(id);
    });
    return this.localStream;
  };

  UidRtcRoom.prototype.muteAudio = function (muted) {
    if (!this.localStream) return;
    this.localStream.getAudioTracks().forEach(function (t) { t.enabled = !muted; });
  };
  UidRtcRoom.prototype.muteVideo = function (muted) {
    if (!this.localStream) return;
    this.localStream.getVideoTracks().forEach(function (t) { t.enabled = !muted; });
  };

  UidRtcRoom.prototype.stopMedia = async function () {
    if (!this.localStream) return;
    var self = this;
    this.localStream.getTracks().forEach(function (track) {
      track.stop();
      Object.keys(self.pcs).forEach(function (id) {
        self.pcs[id].getSenders().forEach(function (sender) {
          if (sender.track && sender.track.id === track.id) {
            try { self.pcs[id].removeTrack(sender); } catch (_) {}
          }
        });
      });
    });
    this.localStream = null;
    Object.keys(this.pcs).forEach(function (id) {
      if (self.peer < id) self._negotiate(id);
    });
  };

  /**
   * ICE restart — call after network change (wifi→lte).
   * Renegotiates with iceRestart so new candidates flow.
   */
  UidRtcRoom.prototype.restartIce = async function (remoteId) {
    var ids = remoteId ? [remoteId] : Object.keys(this.pcs);
    var self = this;
    for (var i = 0; i < ids.length; i++) {
      var id = ids[i];
      var pc = self.pcs[id];
      if (!pc) continue;
      try {
        if (typeof pc.restartIce === "function") pc.restartIce();
      } catch (_) {}
      if (self.peer < id || remoteId) {
        await self._negotiate(id);
      }
    }
  };


  /** P2: cap outbound video bitrate (kbps) via RTCRtpSender. */
  UidRtcRoom.prototype.setVideoBitrate = async function (kbps) {
    var self = this;
    var max = Math.max(50, Number(kbps) || 0) * 1000;
    var tasks = [];
    Object.keys(this.pcs).forEach(function (id) {
      self.pcs[id].getSenders().forEach(function (sender) {
        if (!sender.track || sender.track.kind !== "video") return;
        var params = sender.getParameters();
        if (!params.encodings || !params.encodings.length) {
          params.encodings = [{}];
        }
        params.encodings.forEach(function (enc) {
          enc.maxBitrate = max;
        });
        tasks.push(sender.setParameters(params));
      });
    });
    await Promise.all(tasks.map(function (p) { return p.catch(function () {}); }));
  };

  /** Enable/disable all video encoding layers (simulcast-friendly). */
  UidRtcRoom.prototype.setEncodingActive = async function (active) {
    var self = this;
    var on = active !== false;
    var tasks = [];
    Object.keys(this.pcs).forEach(function (id) {
      self.pcs[id].getSenders().forEach(function (sender) {
        if (!sender.track || sender.track.kind !== "video") return;
        var params = sender.getParameters();
        if (!params.encodings || !params.encodings.length) return;
        params.encodings.forEach(function (enc) { enc.active = on; });
        tasks.push(sender.setParameters(params));
      });
    });
    await Promise.all(tasks.map(function (p) { return p.catch(function () {}); }));
  };

  /**
   * Toggle simulcast layers by rid ("q"|"h"|"f") or index.
   * @param {{q?:boolean,h?:boolean,f?:boolean}|boolean[]} layers
   */
  UidRtcRoom.prototype.setSimulcastLayers = async function (layers) {
    var map = {};
    if (Array.isArray(layers)) {
      map.q = layers[0] !== false;
      map.h = layers[1] !== false;
      map.f = layers[2] !== false;
    } else {
      map = layers || {};
    }
    var self = this;
    var tasks = [];
    Object.keys(this.pcs).forEach(function (id) {
      self.pcs[id].getSenders().forEach(function (sender) {
        if (!sender.track || sender.track.kind !== "video") return;
        var params = sender.getParameters();
        if (!params.encodings || !params.encodings.length) return;
        params.encodings.forEach(function (enc, i) {
          var rid = enc.rid || ["q", "h", "f"][i];
          if (rid && Object.prototype.hasOwnProperty.call(map, rid)) {
            enc.active = !!map[rid];
          }
        });
        tasks.push(sender.setParameters(params));
      });
    });
    await Promise.all(tasks.map(function (p) { return p.catch(function () {}); }));
  };

  UidRtcRoom.prototype.leave = async function () {
    this._alive = false;
    if (this._timer) clearInterval(this._timer);
    this._dcBroadcastQ = [];
    this._dcQueues = Object.create(null);
    try { await this.stopMedia(); } catch (_) {}
    var self = this;
    Object.keys(this.pcs).forEach(function (id) { self._dropPeer(id); });
    try {
      if (this._ws && this._ws.readyState === 1) {
        this._ws.send(JSON.stringify({ op: "leave", room: this.room, peer: this.peer }));
        this._ws.close();
      } else {
        await this._postHttp({ op: "leave", room: this.room, peer: this.peer });
      }
    } catch (_) {}
  };

  /** Fetch short-lived TURN via authenticated iceUrl (ticket header). */
  UidRtcRoom.prototype._refreshIce = async function () {
    var url = this.iceUrl;
    if (!url && typeof document !== "undefined" && document.body) {
      url = document.body.getAttribute("data-channel-webrtc-ice-url") || "";
    }
    if (!url) return;
    try {
      var q = (url.indexOf("?") >= 0 ? "&" : "?") + "room=" + encodeURIComponent(this.room);
      if (this.ticket) q += "&ticket=" + encodeURIComponent(this.ticket);
      var res = await fetch(url + q, {
        credentials: "same-origin",
        headers: this._headers(),
      });
      if (!res.ok) {
        this.onError({ phase: "ice", status: res.status });
        return;
      }
      var data = await json(res);
      if (data && data.iceServers && data.iceServers.length) {
        this.iceServers = data.iceServers;
      }
    } catch (e) {
      this.onError({ phase: "ice", error: String(e) });
    }
  };

  UidRtcRoom.prototype.start = async function () {
    await this._refreshIce();
    if (this.media) {
      try { await this.startMedia(this.media); }
      catch (e) { this.onError({ phase: "media", error: String(e) }); }
    }
    var wsOk = await this._connectWs();
    if (!wsOk) {
      await this._poll();
      var self = this;
      this._timer = setInterval(function () { self._poll(); }, this.opts.pollMs || POLL_MS);
    } else {
      // light presence refresh even on WS
      var self2 = this;
      this._timer = setInterval(function () {
        if (self2._ws && self2._ws.readyState === 1) {
          self2._ws.send(JSON.stringify({ op: "poll", since: self2.since }));
        } else {
          self2._poll();
        }
      }, Math.max(5000, (this.opts.pollMs || POLL_MS) * 6));
    }
    return this;
  };

  var UxWebRTC = {
    version: WEBRTC_VERSION,
    /** Same kinds as Python SIGNAL_KINDS */
    SIGNAL_KINDS: ["offer", "answer", "ice", "ice-done"],
    join: async function (opts) {
      var room = new UidRtcRoom(opts || {});
      await room.start();
      return room;
    },
    Room: UidRtcRoom,
    parseMediaAttr: function (v) { return normalizeMedia(v); },
    /**
     * Browser WebRTC cannot pin peer DTLS certificates from JS (no public API).
     * Use tickets + origin + TURN policy; SFU TLS for server media path.
     */
    securityNotes: function () {
      return {
        dtlsPinning: false,
        dtlsPinningReason:
          "Browsers do not expose WebRTC DTLS certificate pinning to web apps. " +
          "Trust is DTLS-SRTP between peers (or peer↔SFU). Pin the *signaling* HTTPS cert " +
          "and authorize rooms with tickets instead.",
        iceTransportPolicy: ["all", "relay"],
        simulcast: "join({ simulcast: true }) then setSimulcastLayers({q,h,f})",
        signalKinds: ["offer", "answer", "ice", "ice-done"],
        iceRule: "iceServers=html STUN; iceUrl=live TURN with ticket",
        recommendations: [
          "HTTPS + webrtc_require_ticket + webrtc_require_origin",
          "public_ice_servers only in HTML; fetch TURN via iceUrl /rtc/ice",
          "iceTransportPolicy: 'relay' when IP privacy required",
          "Treat data-channel peers as untrusted input",
        ],
      };
    },
  };

  if (global.UxWebRTC && global.__UX_WEBRTC_LOADED__) {
    try { console.warn("[ux-webrtc] already loaded — skip re-bind"); } catch (e0) {}
    return;
  }
  global.__UX_WEBRTC_LOADED__ = true;
  global.UxWebRTC = UxWebRTC;

  function bootAuto() {
    var el = document.body;
    if (!el || !el.hasAttribute("data-channel-webrtc-auto")) return;
    var rtc = el.getAttribute("data-channel-webrtc-rtc") || "/ux-channel/rtc";
    var ws = el.getAttribute("data-channel-webrtc-ws") || "";
    var roomName = el.getAttribute("data-channel-webrtc-room") || "default";
    var mediaAttr = el.getAttribute("data-channel-webrtc-media");
    var ticket = el.getAttribute("data-channel-webrtc-ticket") || "";
    var ice = parseIceAttr(el.getAttribute("data-channel-webrtc-ice"));
    var iceUrl = el.getAttribute("data-channel-webrtc-ice-url") || "";
    UxWebRTC.join({
      rtcPath: rtc,
      wsPath: ws || undefined,
      room: roomName,
      ticket: ticket || undefined,
      iceServers: ice || undefined,
      iceUrl: iceUrl || undefined,
      media: mediaAttr ? normalizeMedia(mediaAttr) : null,
      onMessage: function (from, data) {
        try {
          document.dispatchEvent(new CustomEvent("ux-webrtc-message", { detail: { from: from, data: data } }));
        } catch (_) {}
      },
      onPeer: function (id, state) {
        try {
          document.dispatchEvent(new CustomEvent("ux-webrtc-peer", { detail: { peer: id, state: state } }));
        } catch (_) {}
      },
      onTrack: function (id, stream, track) {
        try {
          document.dispatchEvent(new CustomEvent("ux-webrtc-track", { detail: { peer: id, stream: stream, track: track } }));
        } catch (_) {}
      },
      onLocalStream: function (stream) {
        try {
          document.dispatchEvent(new CustomEvent("ux-webrtc-local", { detail: { stream: stream } }));
        } catch (_) {}
      },
    }).then(function (room) { global.__uidWebRtcRoom = room; });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootAuto);
  } else {
    bootAuto();
  }
})(typeof window !== "undefined" ? window : globalThis);
