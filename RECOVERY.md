# COMPLETE HARDENED REPO — NOTHING LOST

## Instant recover (GitHub only)

```bash
git clone https://github.com/bitplorer/ux-channel.git && cd ux-channel
bash scripts/apply-hardening.sh
# or:
curl -sL https://raw.githubusercontent.com/bitplorer/ux-channel/main/patches/0001-production-hardening-authz-seal.patch | git am
```

## Full tree backup (agent artifacts — download before session ends)

| File | Contents |
|------|----------|
| `ux-channel-FULL-HARDENED.zip` | **Complete** 830-file tree with all hardenings (~2.3 MB) |
| `ux-channel-FULL-HARDENED.bundle` | Git bundle of hardened tip (~2.1 MB) |
| `PRESERVE-HARDENED/` | Critical hardened `.py` sources |
| `0001-FULL-HARDENING-*.patch` | Same delta as `patches/` on main |

```bash
unzip ux-channel-FULL-HARDENED.zip && cd uxc
# or
git clone ux-channel-FULL-HARDENED.bundle recovered-ux-channel
```

## What is hardened

**Already as source on main:** rate-limit fail-closed, idempotency fail-closed, roles_of principal-only, MCP sessions max_sessions.

**In the patch / FULL zip:** registry principal id-only, regions/flow no client roles, agent confirm fail-closed, webrtc defaults fail-closed.

Local hardened commit: `241424f`
