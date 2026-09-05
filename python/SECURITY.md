# Security (Python host)

Family policy: [../../SECURITY.md](../../SECURITY.md).
Full audit: [docs/security/SECURITY_AUDIT.md](docs/security/SECURITY_AUDIT.md).

## Defaults that are unsafe in production

| Door | Development | Production |
|------|-------------|------------|
| Secret | `ChannelConfig.development(secret="dev-" + "x"*32)` | Long random secret from the environment; never commit |
| CEK | `cek=require` (default; cek-runtime Host) | Same default. Escape: `cek=off` / `UX_CHANNEL_CEK=off` for classic CapService |
| DX | warnings | `export UX_CHANNEL_STRICT_DX=1` and `uxchannel doctor --fail` |

## Invariants (fail closed)

1. Unknown action → `ActionNotFound`.
2. Bad / missing Cap on a protected action → `CapError`.
3. JTI reuse → rejected (once).
4. `args_hash` mismatch → rejected.
5. `dispatch()` refuses `async def` handlers. Use `await registry.async_dispatch(...)`.

## Reporting

Same path as [SECURITY.md](../../SECURITY.md).
