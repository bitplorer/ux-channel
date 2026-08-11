# Hardening status — do not lose

## Recover without this agent session

```bash
# From GitHub (this file + patch):
curl -sL https://raw.githubusercontent.com/bitplorer/ux-channel/main/patches/0001-production-hardening-authz-seal.patch | git am

# Or from agent artifacts (if still present):
unzip ux-channel-hardening-critical.zip
# copy *.py into tree
git am 0001-Production-hardening-authz-seal-fail-closed-stores-a.patch
```

## Already applied on main (connector)

- MemoryRateLimiter fail-closed when full
- MemoryIdempotencyStore fail-closed when full
- roles_of: principal claims/scopes only
- MemoryMcpSessionStore max_sessions fail-closed

## In the patch (apply with git am)

- Soft principal: **id only** (no client roles)
- ActionContext.meta: no client roles
- RegionBook / flow: no client roles into scope
- AgentRunner confirm: signed secret required (fail closed)
- WebRTC ticket/origin defaults fail-closed (development opts out)

## Local artifacts (agent workspace)

- `/home/workdir/artifacts/ux-channel-hardened/` — hardened source files
- `/home/workdir/artifacts/ux-channel-hardening-critical.zip`
- `/home/workdir/artifacts/0001-Production-hardening-authz-seal-fail-closed-stores-a.patch`
