# Enterprise notes — uxchannel 0.1

- Always derive **tenant / user** from server session / `Principal`, never from client-only args without membership checks.
- Prefer `trust_*` for sealed resource ids on controls.
- Multi-worker: shared Redis for once-caps, idempotency, rate limits, draft if shared.
- Audit: `@ch.on(..., audit=True)` + `ch.audit` / after-hooks.
- See [SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md) · [PRODUCTION.md](PRODUCTION.md).
