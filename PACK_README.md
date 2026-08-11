# ux-channel — complete hardened snapshot notes

This tree is the production-hardening snapshot of the monorepo. Prefer Git history on [bitplorer/ux-channel](https://github.com/bitplorer/ux-channel) as the durable source.

## Quick start

```bash
git clone https://github.com/bitplorer/ux-channel.git
cd ux-channel
make verify
```

If you unpacked a zip bootstrap:

```bash
cd ux-channel
make regen      # refresh derived catalog / map fields
make verify
git remote add origin <your-remote>   # if starting fresh
git push -u origin main
```

## Hardenings included

- Soft principal: id only (no client roles from Intent)  
- registry meta / regions / flow: strip client roles  
- AgentRunner: confirmation requires signed secret (fail closed)  
- WebRTC ticket + origin fail-closed defaults  
- MCP sessions `max_sessions` fail-closed  
- Rate limit + idempotency fail-closed stores  
- `roles_of`: principal claims only  

## Apply delta only onto upstream main

```bash
bash scripts/apply-hardening.sh
# or
curl -sL https://raw.githubusercontent.com/bitplorer/ux-channel/main/patches/0001-production-hardening-authz-seal.patch | git am
```

See [RECOVERY.md](RECOVERY.md), [HARDENING_STATUS.md](HARDENING_STATUS.md), [AUTOMATION.md](AUTOMATION.md).
