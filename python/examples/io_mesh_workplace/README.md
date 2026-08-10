# Workplace · I/O mesh demo

Uses **`workplace(ch, ticket=…)`** for claim-aware I/O + agents.

| Surface | Demo |
|---------|------|
| `wp.dispatch` / button / scan | A1 cart |
| Party claim TTL + lights | A2 |
| Lab `run_io` + Quantity | A3 |
| `/api/situation` | claim-filtered tools + snapshot |
| `/api/io-audit` | I/O policy tape |

```bash
PYTHONPATH=src uvicorn examples.io_mesh_workplace.app:app --host 0.0.0.0 --port 8080
```

Docs: [WORKPLACE.md](../../docs/workplace/WORKPLACE.md) · [IO_CHANNEL.md](../../docs/workplace/IO_CHANNEL.md)
