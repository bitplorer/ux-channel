# Hardening status — NOTHING LOST

See **RECOVERY.md** for full restore paths.

## Durable copies

1. **GitHub** `patches/0001-production-hardening-authz-seal.patch` + `RECOVERY.md`
2. **Artifacts** `ux-channel-FULL-HARDENED.zip` (complete 830-file tree)
3. **Artifacts** `ux-channel-FULL-HARDENED.bundle` (git cloneable)
4. **Artifacts** `PRESERVE-HARDENED/` critical sources

## Apply on any machine

```bash
curl -sL https://raw.githubusercontent.com/bitplorer/ux-channel/main/patches/0001-production-hardening-authz-seal.patch | git am
```
