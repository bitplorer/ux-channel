# Workplace starter kit

Copy-paste deploy target: [`examples/workplace_kit/`](../examples/workplace_kit/).

## What it includes

| Piece | |
|-------|--|
| Channel boot | env-driven prod/dev |
| Mesh membership | `issue_mesh_membership` |
| Workplace | claim-aware control / dispatch |
| Quantity | cart pay from store |
| Outbox | queue + drain offline Intents |
| MCP | optional agent tools (`mount_agent_mcp`) |
| Audit | `/api/audit` |

## Run

```bash
cd uxchannel PYTHONPATH=src uvicorn examples.workplace_kit.app:app --host 0.0.0.0 --port 8080
```

Production-shaped:

```bash
export UX_CHANNEL_ENV=production
export UX_CHANNEL_SECRET='…long…'
export REDIS_URL=redis://…
export UX_CHANNEL_AGENT_TOKEN='…'
export UX_CHANNEL_ORIGIN=https://your.app
PYTHONPATH=src uvicorn examples.workplace_kit.app:app --host 0.0.0.0 --port 8080
```

## Deploy notes (generic)

1. Build/install package + set env vars above  
2. Single web process → `uvicorn` / gunicorn+uvicorn workers **with Redis**  
3. Put TLS terminator in front; set origin allowlist  
4. MCP only on private network or with strong `agent_token`  

Vercel/serverless: prefer long-lived worker for outbox drain + WebRTC; kit is **process-oriented**.

## Related

[PRODUCTION_CHECKLIST.md](../production/PRODUCTION_CHECKLIST.md) · [OUTBOX.md](OUTBOX.md) · [MCP_VERTICALS.md](../agents/MCP_VERTICALS.md) · [THREE_SURFACES.md](THREE_SURFACES.md)
