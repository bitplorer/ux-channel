<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Production checklist (0.1)

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | `uxchannel` |

Use with a real workplace app ([workplace_pos](../../examples/workplace_pos/), [workplace_lab](../../examples/workplace_lab/)).

## Secret & env

- [ ] Strong `UX_CHANNEL_SECRET` (not the demo default)
- [ ] `UX_CHANNEL_ENV=production` (or `ChannelConfig.production`)
- [ ] `require_cap=True`
- [ ] `require_channel_header=True` (client always sends `X-Channel: 1`)
- [ ] Origin allowlist + `enforce_same_origin=True` for browser apps

## Durable stores

- [ ] `REDIS_URL` for multi-worker nonce / idempotency / rate / revoke
- [ ] Do **not** leave `allow_memory_stores=True` across multiple workers

## Membership

- [ ] Mint with `issue_mesh_membership` / `ch.webrtc.issue_membership` (server scopes)
- [ ] Never accept scopes from the browser
- [ ] Logout calls `revoke_mesh_membership(mem)`
- [ ] Short `max_age` / ticket TTL

## Quantity

- [ ] High-stakes values via `Quantity.from_store` only
- [ ] Chrome holds ids, not magnitudes

## Surfaces

- [ ] UI: `wp.control` (claim-aware)
- [ ] Agents: `wp.dispatch` / `wp.tools_for`
- [ ] Devices: adapter → `check_event` → same action  
  See [THREE_SURFACES.md](../workplace/THREE_SURFACES.md)

## Audit & support

- [ ] `attach_audit(ch)` on
- [ ] Export path for intent log + `wp.export_io_audit()`
- [ ] Security events reviewed (`ch.security_events` / logs)

## WebRTC (if used)

- [ ] `webrtc_require_ticket=True` for private rooms
- [ ] Prefer TURN for real NATs
- [ ] Media tickets ≠ policy scopes (`workplace_from_rtc(..., scopes=policy)`)

## Freeze

Stay inside [FREEZE_0.1.md](../start/FREEZE_0.1.md). New product APIs only if a real app is blocked.

## Ops

[WORKPLACE_OPS.md](../workplace/WORKPLACE_OPS.md) · [SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md) · [PRODUCTION.md](PRODUCTION.md)
