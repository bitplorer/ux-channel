# ux-channel — COMPLETE HARDENED snapshot

Full tree with production hardenings applied. Use this zip in another conversation or machine.

## Quick start

```bash
unzip ux-channel-COMPLETE-HARDENED.zip
cd ux-channel
# init git if needed
git init
git add -A
git commit -m "ux-channel complete hardened snapshot"
git remote add origin <your-remote>
git push -u origin main
```

## Hardenings included

- Soft principal: id only (no client roles from Intent)
- registry meta / regions / flow: strip client roles
- AgentRunner: confirmation requires signed secret (fail closed)
- WebRTC ticket + origin fail-closed defaults
- MCP sessions max_sessions fail-closed
- Rate limit + idempotency fail-closed stores
- roles_of: principal claims only

## Apply delta only onto upstream main

```bash
bash scripts/apply-hardening.sh
# or
curl -sL https://raw.githubusercontent.com/bitplorer/ux-channel/main/patches/0001-production-hardening-authz-seal.patch | git am
```

See RECOVERY.md and HARDENING_STATUS.md for details.
