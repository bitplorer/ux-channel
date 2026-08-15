<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Standards & RFC alignment

uxchannel is **not** a SIP stack, SFU, or browser. It implements a small
**application control plane** plus **WebRTC signaling ferry**. This document
maps each surface to external standards and states **what we implement**,
**what we deliberately leave out**, and **who owns the rest**.

## Philosophy (boundary)

| Layer | Owner | Standard role |
|-------|--------|----------------|
| Intent / Result / ops | uxchannel | App protocol (`uid: "1"`) — not an IETF RFC |
| Capabilities (HMAC caps) | uxchannel | AuthZ tokens (itsdangerous-shaped), not OAuth/JWT by default |
| HTML morph / regions | **Host UI** | DOM — out of library scope |
| WebRTC media & DTLS | **Browser** | W3C WebRTC, DTLS-SRTP |
| Mesh signaling ferry | uxchannel | Carries JSEP objects; not JSEP itself |
| ICE connectivity | Browser + TURN | RFC 8445 / 8838; we only relay candidates |
| TURN credentials | uxchannel mint + coturn | de-facto coturn REST; not a TURN server |
| SFU / WHIP media | External / optional adapters | draft-ietf-wish-whip inspired helpers only |

---

## WebRTC / JSEP / ICE

| Spec | Compliance |
|------|------------|
| **JSEP** (browser offer/answer) | Client uses `RTCPeerConnection` APIs; server **stores and forwards** `RTCSessionDescriptionInit` JSON |
| **SDP** (RFC 8866-ish) | Lightweight check: offer/answer require string `sdp` containing `v=`; **not** a full SDP parser |
| **ICE** (RFC 8445) | Candidates are opaque JSON (`RTCIceCandidateInit`); connectivity is browser-side |
| **Trickle ICE** (RFC 8838) | Supported: many `kind=ice` messages; **`kind=ice-done`** with null payload → client `addIceCandidate(null)` end-of-candidates |
| **DTLS-SRTP / SCTP data** | Browser only; server never sees media bytes |
| **Perfect negotiation** | Client polite/impolite by peer id (application pattern, not an RFC) |

**Wire kinds (application):** `offer | answer | ice | ice-done`  
Validated by `validate_signal_payload()` before store.

**Transports (signaling-agnostic by design):**

* `GET/POST /ux-channel/rtc` — JSON, `Cache-Control: no-store`
* `WS /ux-channel/rtc/ws` — same kinds (RFC 6455 WebSocket)

Not claimed: SIP (RFC 3261), Jingle, full WHIP media ingestion.

---

## ICE services / TURN

| Spec / practice | Role |
|-----------------|------|
| STUN | Default public servers in `ice.html()` |
| TURN (RFC 8656) | Relay via **your** coturn; we mint credentials only |
| coturn static-auth-secret / REST | `UX_CHANNEL_TURN_SECRET` → time-bound username/credential |
| HTML embedding | **Forbidden** for credentials — `ice.html()` only |

---

## HTTP / SSE / WebSocket (control plane)

| Surface | Standard | Notes |
|---------|----------|--------|
| Action POST | JSON HTTP | `application/json`; optional custom channel header (CSRF) |
| SSE push | HTML SSE (`text/event-stream`) | Server → client ops |
| Ops WebSocket | RFC 6455 | Separate from RTC WS path |
| RTC JSON | `application/json` + `no-store` | No caching of tickets/signals |
| Origin | Browser Origin / same-origin policy | `webrtc_require_origin`, action origin checks |

---

## WHIP / WHEP (optional)

| Draft | Our stance |
|-------|------------|
| draft-ietf-wish-whip / whep | **Helpers only** (`ux_channel.whip`) when `whip_enabled` — not a complete media ingestion server |
| Production broadcast | Use `ux_channel.sfu` → LiveKit/etc. |

---

## App protocol (`uid: "1"`)

Intent/Result is a **versioned application schema**, not an RFC. Stability rules:

* Unknown ops should be ignored by clients where possible
* Caps bind action + args hash (integrity), not encryption
* Confidentiality on the wire = **HTTPS/WSS** (deploy)

---

## Explicit non-goals (SoC)

* Rendering / design systems  
* Being the media path  
* Full SDP rewriting / BUNDLE policy engines  
* OAuth2 AS / OIDC OP  
* Multiparty SFU congestion control  

---

## Verification

* Unit: `validate_signal_payload`, RTC HTTP, tickets, ICE html/live  
* Integration: pytest suite (`tests/test_webrtc*.py`, `test_standards_compliance.py`)  
* Browser: JSEP/ICE behavior is the platform’s; we ferry JSON faithfully  

See also [WEBRTC_SIGNALING.md](../webrtc/WEBRTC_SIGNALING.md) · [WEBRTC_SECURITY.md](../webrtc/WEBRTC_SECURITY.md) · [API_SURFACE.md](../start/API_SURFACE.md).
