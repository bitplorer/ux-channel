# COMPLETE HARDENED REPO — RECOVERY

## On agent artifacts (this workspace)

| Artifact | Size | Use |
|----------|------|-----|
| `ux-channel-FULL-HARDENED.zip` | ~2.3 MB | Full tree (830 files), no .git |
| `ux-channel-FULL-HARDENED.bundle` | ~2.1 MB | `git clone ux-channel-FULL-HARDENED.bundle recovered` |
| `0001-FULL-HARDENING-*.patch` | 8 KB | `git am` onto clean main |
| `PRESERVE-HARDENED/` | sources | Direct copy of hardened .py files |
| `patches/0001-production-hardening-authz-seal.patch` (this repo) | on main | same patch online |

## Restore full tree

```bash
unzip ux-channel-FULL-HARDENED.zip
cd uxc
# OR from bundle:
git clone ux-channel-FULL-HARDENED.bundle ux-channel-recovered
```

## Apply only the hardening delta onto latest main

```bash
git clone https://github.com/bitplorer/ux-channel.git
cd ux-channel
curl -sL https://raw.githubusercontent.com/bitplorer/ux-channel/main/patches/0001-production-hardening-authz-seal.patch | git am
```

## Hardening inventory

Already on main as source:
- rate limit fail-closed
- idempotency fail-closed
- roles_of principal-only
- MCP sessions max_sessions

In the patch / FULL zip (must apply or unzip):
- registry soft principal id-only
- regions/flow no client roles
- agent confirm fail-closed
- webrtc ticket/origin fail-closed defaults

Local hardened commit: 241424f
