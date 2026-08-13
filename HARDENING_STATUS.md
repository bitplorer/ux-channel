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

### Authz seal (0.1)
- `MemoryRateLimiter` fail-closed when full  
- `MemoryIdempotencyStore` fail-closed when full  
- `roles_of`: principal claims/scopes only  
- `MemoryMcpSessionStore` `max_sessions` fail-closed  
- Soft principal: **id only** (no client roles from Intent)  
- `ActionContext.meta`: no client roles  
- RegionBook / flow: no client roles into scope  
- AgentRunner confirm: signed secret required (fail closed)  
- WebRTC ticket/origin defaults fail-closed (development may opt out)  

### Deeper hardening (post-seal)
- **cap.sub overrides soft principal** when args `user_id` disagrees with signed sub  
- **Security events**: `role_claim_ignored`, `principal_mismatch`, `rate_limited`, `agent_confirm_denied`  
- **Production** `ws_require_origin=True` (service clients may opt out)  
- **Production** derives `navigate_allowed_hosts` from `allowed_origins` when not set (open-redirect control)  
- Gate suite: [`python/tests/gate/test_deeper_hardening.py`](python/tests/gate/test_deeper_hardening.py)

### Architecture plane (IR 0.1 floor)
- once/jti consume is live on Python `CapService.verify` and Rust `mint_once`
- Channel.boot installs a process-local nonce store in development
- present-cap-must-verify on ActionRegistry and ArchRegistry
- proofs fail closed (`proofs=require` without a key emits zero ops)
- Gate suite: [`python/tests/gate/test_arch_e2e.py`](python/tests/gate/test_arch_e2e.py)

## Verify after any restore

```bash
make verify
# security-focused:
cd python && PYTHONPATH=src python3 -m pytest tests/gate/test_deeper_hardening.py tests/security -q
```

Do not treat chat-session artifacts as the canonical tree — commit to GitHub and re-run automation ([AUTOMATION.md](AUTOMATION.md)).
