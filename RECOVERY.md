# Hardening recovery — durable sources only

**Source of truth is GitHub `main`**, not a chat session or sandbox zip.

## Preferred: already on main

The complete hardened tree is the current default branch:

```bash
git clone https://github.com/bitplorer/ux-channel.git
cd ux-channel
make verify
```

## Apply only the authz-seal patch onto a clean fork of law

```bash
git clone https://github.com/bitplorer/ux-channel.git
cd ux-channel
curl -sL https://raw.githubusercontent.com/bitplorer/ux-channel/main/patches/0001-production-hardening-authz-seal.patch | git am
# or:
bash scripts/apply-hardening.sh
```

Patch lives in-repo: [`patches/0001-production-hardening-authz-seal.patch`](patches/0001-production-hardening-authz-seal.patch).

## Hardening inventory

| Area | Status |
|------|--------|
| Rate limit / idempotency stores fail-closed when full | on `main` |
| `roles_of`: principal claims only | on `main` |
| MCP sessions `max_sessions` fail-closed | on `main` |
| Soft principal: **id only** (no client roles) | on `main` / patch |
| RegionBook / flow: no client roles into scope | on `main` / patch |
| AgentRunner confirm: signed secret required | on `main` / patch |
| WebRTC ticket/origin defaults fail-closed | on `main` / patch |
| cap.sub overrides soft principal from args | on `main` |
| Production `ws_require_origin` + navigate host derive | on `main` |
| Security events (role claim / rate / agent confirm) | on `main` |

Details: [HARDENING_STATUS.md](HARDENING_STATUS.md) · policy: [AUTOMATION.md](AUTOMATION.md).

## Do not rely on

- Agent sandbox paths or one-off workspace zips as the long-term archive  
- Hand-editing generated catalog / map fields after a partial copy  

If you received a snapshot zip, treat it as a **bootstrap**, then re-verify with `make verify` and push to your remote so Git history is the recovery mechanism.
