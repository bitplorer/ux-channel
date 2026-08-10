# Inspector & trace — uxchannel 0.1

Development can enable action/bridge tracing:

- Config: `trace_enabled`, `trace_http`, `trace_token`, `trace_capture_payloads`
- Client: `ux-inspector.js` (included in dev `ch.scripts()` when configured)
- HTTP: `GET /ux-channel/trace` (denied in production without token)

**Production:** leave trace off or require a strong `trace_token`. Never enable payload capture on public internet.
