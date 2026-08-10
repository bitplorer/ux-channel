# Workplace ops & security notes

Short checklist for running policy-shaped rooms safely.

## Membership

| Do | Don't |
|----|--------|
| Mint tickets **on the server** (`sign_workplace_ticket`) | Let the browser choose `scopes` |
| Bind `room` + `sub` + attenuated scopes | Treat “on WebRTC” as trust |
| Set `max_age` / check `claim.alive()` | Use immortal tickets |
| Re-mint on role change (`wp.mint_ticket` / `rebind`) | Widen scopes on rebind |

## Caps & UI

| Do | Don't |
|----|--------|
| `require_cap=True` in production | Open actions without caps |
| Prefer `wp.control` when a Workplace is bound | Mint controls wider than claim |
| Same actions for button / agent / scan | Backdoor agent I/O API |

## Quantity

| Do | Don't |
|----|--------|
| `Quantity.from_store` after durable load | Put amounts in session/client |
| Put ids in ticket `trust` | Put magnitudes in ticket trust |

## I/O

| Do | Don't |
|----|--------|
| Adapters outside core | Drivers in `uxchannel` |
| `wp.run_io` / `run_checked` + audit | Raw adapter calls without gate |
| STREAM via media plane | High-rate loops on Intent path |

## Tickets vs WebRTC

| Ticket | Role |
|--------|------|
| **Workplace ticket** | Policy membership (`scopes`) |
| **RTC ticket** | Media door (room/sub); scopes from **server policy** via `claim_from_rtc_ticket` |

## Config knobs

* `secret` — required for tickets  
* `workplace_ticket_max_age` (optional; else `webrtc_ticket_max_age` / 300s)  
* `require_cap=True`  
* `audit=True` / `attach_audit`  

## Incident basics

1. Revoke / stop minting tickets for `sub`  
2. Export `wp.export_io_audit()` + intent log  
3. Narrow room scopes; re-issue tickets  

See [WORKPLACE.md](WORKPLACE.md) · [IO_CHANNEL.md](IO_CHANNEL.md) · [SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md).

## Mesh issuance

Prefer `issue_mesh_membership` so RTC and workplace tickets share room/sub.
Never accept scopes from the client. Re-issue on role change via `/api/membership` pattern.

## Logout / ban

```python
revoke_mesh_membership(mem, channel=ch)
# or wp.revoke_membership() when built from ticket_token / membership
```

Revoked tickets fail verify (workplace + RTC).
