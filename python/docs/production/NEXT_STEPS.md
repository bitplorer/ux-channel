<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Next steps — status (0.1.x)

## Done in library

| Item | Status |
|------|--------|
| Redis multi-worker RTC | `RedisRtcStore` |
| Tickets + origin prod defaults | `production()` |
| Rate limit / peer sanitize | `/rtc` gate |
| Plugin DX (no UI chrome) | `ch.webrtc.plugin()` |
| Short-lived TURN mint | `webrtc_turn` + `GET /ux-channel/rtc/ice` |
| Client `iceUrl` refresh | `ux-webrtc.js` |
| Simulcast helpers | client API |
| WHIP / SFU adapters | optional layers |

## Your deploy checklist

1. **HTTPS** + strong `UX_CHANNEL_SECRET`
2. **Redis** if workers > 1
3. **Coturn** with `static-auth-secret` → `UX_CHANNEL_TURN_SECRET` + `UX_CHANNEL_TURN_URLS`
4. Mint page tickets: `ch.webrtc.sign_ticket(room, sub=user)`
5. Host UI places `plugin()` only — no TURN passwords in HTML

## Optional later

| Item | Note |
|------|------|
| Multi-region RTC store | beyond single Redis |
| Full SFU product | use LiveKit adapter; not mesh |
| Browser E2E CI with fake media | Playwright job |
| 0.1.0 PyPI publish | tag + twine |

## Docs

[WEBRTC_DX.md](../webrtc/WEBRTC_DX.md) · [WEBRTC_SECURITY.md](../webrtc/WEBRTC_SECURITY.md) · [API_SURFACE.md](../start/API_SURFACE.md)
