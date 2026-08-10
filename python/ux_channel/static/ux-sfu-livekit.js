/**
 * ux-sfu-livekit.js — tiny boot for LiveKit via uxchannel media plugin.
 *
 * Does NOT reimplement WebRTC. Loads join opts from #ux-media-client and
 * calls livekit-client Room.connect. Prefer bundling livekit-client in apps;
 * CDN script tags are optional DX for demos.
 *
 * Wire: channel mints token → this file connects → tracks are host's to attach.
 */
(function (global) {
  "use strict";

  var BOOT_ATTR = "data-channel-media-autoboot";

  function readClient() {
    var el = document.getElementById("ux-media-client");
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (e) {
      return null;
    }
  }

  function pickLiveKit() {
    // UMD global variants
    if (global.LivekitClient) return global.LivekitClient;
    if (global.LiveKit) return global.LiveKit;
    if (global.livekit) return global.livekit;
    return null;
  }

  async function connect(opts) {
    opts = opts || readClient();
    if (!opts || !opts.url || !opts.token) {
      console.warn("[uid-media] missing url/token — ch.media.plugin(mode='sfu')");
      return null;
    }
    var LK = pickLiveKit();
    if (!LK || !LK.Room) {
      console.warn(
        "[uid-media] livekit-client not found. npm i livekit-client or CDN UMD build."
      );
      return null;
    }
    var room = new LK.Room(opts.roomOptions || {});
    room.on(LK.RoomEvent.TrackSubscribed, function (track, pub, participant) {
      try {
        document.dispatchEvent(
          new CustomEvent("uid-media-track", {
            detail: { track: track, participant: participant, publication: pub },
          })
        );
      } catch (_) {}
      // Auto-attach if host provides sinks
      var audio = document.querySelector("[data-channel-media-audio='" + participant.identity + "']");
      var video = document.querySelector("[data-channel-media-video='" + participant.identity + "']");
      if (track.kind === "audio" && audio) track.attach(audio);
      if (track.kind === "video" && video) track.attach(video);
      var remote = document.querySelector("[data-channel-media-remote]");
      if (remote && track.kind === "video") track.attach(remote);
    });
    room.on(LK.RoomEvent.LocalTrackPublished, function (pub) {
      try {
        document.dispatchEvent(
          new CustomEvent("uid-media-local", { detail: { publication: pub } })
        );
      } catch (_) {}
      var local = document.querySelector("[data-channel-media-local]");
      if (local && pub.track && pub.track.kind === "video") pub.track.attach(local);
    });
    await room.connect(opts.url, opts.token);
    if (opts.canPublish !== false && LK.createLocalTracks) {
      try {
        var tracks = await LK.createLocalTracks({ audio: true, video: true });
        await Promise.all(tracks.map(function (t) { return room.localParticipant.publishTrack(t); }));
      } catch (e) {
        console.warn("[uid-media] publish local tracks:", e);
      }
    }
    global.__uidMediaRoom = room;
    try {
      document.dispatchEvent(new CustomEvent("uid-media-connected", { detail: { room: room } }));
    } catch (_) {}
    return room;
  }

  function boot() {
    var body = document.body;
    if (body && body.getAttribute("data-channel-media-mode") === "sfu") {
      // autoboot when mode=sfu unless data-channel-media-autoboot="false"
      if (body.getAttribute(BOOT_ATTR) === "false") return;
      connect();
    }
  }

  global.UidMedia = {
    connect: connect,
    readClient: readClient,
    provider: "livekit",
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})(typeof window !== "undefined" ? window : globalThis);
