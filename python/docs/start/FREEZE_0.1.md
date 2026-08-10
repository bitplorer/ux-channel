# uxchannel 0.1 — surface freeze

## Frozen day-1 (core)

Do not rename or dual-path these without a major version:

* `Channel.boot` · `@ch.region` · `@ch.on` · `ch.control` · `ch.done` / `ch.fail`
* `agents(ch)` · `state(ch)` · `attach_audit`
* Wire: Intent / Result / `uid: "1"` · ops vocabulary
* Caps, CSRF headers, production store requirements

## Frozen power speech (0.1)

| Concept | Canonical import / name |
|---------|-------------------------|
| Measure | `Quantity` · `from_store` · `magnitude` / `unit` / `provenance.revision` |
| Morph paint | `region(uid)` (not slot) |
| I/O channel | `ux_channel.io_channel` — not a driver |
| Workplace | `ux_channel.workplace` (`.ticket` / `.mesh` advanced) |
| Mesh join | `issue_mesh_membership` · `ch.webrtc.issue_membership` · `workplace_from_membership` |
| Membership revoke | `revoke_mesh_membership` / `wp.revoke_membership` |
| AX | `agents(ch)` only |

## Opt-in upgrades (not on root `__all__`)

`quantity` · `io_channel` · `workplace` · `outbox` · `io_adapters` · `morph_ir` · …

Core **boot does not import** these.

## Allowed without unfreeze

* Bugfixes, docs, tests  
* New **adapters** / examples  
* Additive optional kwargs with safe defaults  
* New power modules under import-by-concern  

## Requires major / explicit unfreeze

* Renaming day-1 verbs  
* Second agent product API  
* Drivers in core  
* Breaking wire `uid` / op names  

## References

[API_SURFACE.md](API_SURFACE.md) · [NAMING.md](NAMING.md) · [GOVERNING_STANCE.md](GOVERNING_STANCE.md) · [THREE_SURFACES.md](../workplace/THREE_SURFACES.md)
