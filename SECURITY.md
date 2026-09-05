# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes (best-effort while pre-1.0) |

## Threat model

**ux-channel owns the wire:** `Intent {action, args, cap}` → verify → action → `Result {ok, ops[]}`.

This layer **does** implement Caps (default decide is cek-runtime Host; `cek=off` is the explicit escape), `args_hash`, JTI/once, CSRF as documented, fail-closed unknown actions.

This layer **does not** implement HTML escaping of morph payloads, MorphState, or multi-tenant policy beyond Caps you mint.

Do **not** ship `ChannelConfig.development(secret=…)` in production. Set `UX_CHANNEL_STRICT_DX=1` in CI. Run `uxchannel doctor --fail`.

Deeper: [python/SECURITY.md](python/SECURITY.md), [python/docs/security/SECURITY_AUDIT.md](python/docs/security/SECURITY_AUDIT.md).

## Reporting

GitHub Security Advisory on [bitplorer/ux-channel](https://github.com/bitplorer/ux-channel/security/advisories/new) or **bitplorer@outlook.com** (`ux-channel security`). Include transport and whether CEK was on. Never paste live Caps. Do not file a public issue for unreleased details.
