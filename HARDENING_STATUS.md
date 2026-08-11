# Hardening status

Durable recovery: **[RECOVERY.md](RECOVERY.md)** · GitHub: [bitplorer/ux-channel](https://github.com/bitplorer/ux-channel).

## Apply / re-apply the seal patch

```bash
# From a clone of this repo:
bash scripts/apply-hardening.sh

# Or pull the patch from main:
curl -sL https://raw.githubusercontent.com/bitplorer/ux-channel/main/patches/0001-production-hardening-authz-seal.patch | git am
```

In-tree patch: [`patches/0001-production-hardening-authz-seal.patch`](patches/0001-production-hardening-authz-seal.patch).

## Already applied on main

- `MemoryRateLimiter` fail-closed when full  
- `MemoryIdempotencyStore` fail-closed when full  
- `roles_of`: principal claims/scopes only  
- `MemoryMcpSessionStore` `max_sessions` fail-closed  

## In the seal patch (source on main)

- Soft principal: **id only** (no client roles from Intent)  
- `ActionContext.meta`: no client roles  
- RegionBook / flow: no client roles into scope  
- AgentRunner confirm: signed secret required (fail closed)  
- WebRTC ticket/origin defaults fail-closed (development may opt out)  

## Verify after any restore

```bash
make verify
```

Do not treat chat-session artifacts as the canonical tree — commit to GitHub and re-run automation ([AUTOMATION.md](AUTOMATION.md)).
