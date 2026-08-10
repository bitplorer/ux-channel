# Workplace POS (prod-shaped)

| Feature | |
|---------|--|
| Caps | `require_cap=True` |
| CSRF | `require_channel_header=True` |
| Membership | `issue_mesh_membership` (RTC + workplace tickets) |
| Surfaces | `wp.control` · `wp.dispatch` · scanner event |
| Money | `Quantity.from_store` |
| Audit | `GET /api/audit` |
| Redis | set `REDIS_URL` (+ `UX_CHANNEL_ENV=production`) |

```bash
PYTHONPATH=src uvicorn examples.workplace_pos.app:app --host 0.0.0.0 --port 8080
```

Docs: [THREE_SURFACES.md](../../docs/workplace/THREE_SURFACES.md) · [FREEZE_0.1.md](../../docs/start/FREEZE_0.1.md)
