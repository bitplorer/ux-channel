# ux-channel tests (0.1)

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |

## Layout (collection ≈ dependency order)

| Package | Plane |
|---------|--------|
| `core/` | Intent → Action → Result, registry, control, caps |
| `regions/` | Regions, morph, components |
| `state/` | Server state / draft / SSR |
| `asgi/` | FastAPI mount, batch, hooks, HTML helpers |
| `bridges/` | Bridge contracts, fx/ui, scaffold |
| `client/` | `ux-channel.js`, CSRF headers, wire parity |
| `webrtc/` | WebRTC, ICE, push, websocket security |
| `workplace/` | Workplace, mesh, tickets, I/O, outbox |
| `agents/` | MCP / agent tools |
| `redis_store/` | Redis backends |
| `ux_dom_glue/` | Optional **ux-dom** interop (`ux_channel_ux_dom`) |
| `dx/` | CLI, dashboard, doctor, scaffold |
| `foundations/` | Pillars, waves, properties, golden path |
| `security/` | Pentest, production surface, **0.1 lock** |
| `stress/` | Load / chaos / enterprise stress |

## Run

```bash
PYTHONPATH=src python -m pytest tests/ -q
# focused
PYTHONPATH=src python -m pytest tests/security/test_production_0_1_lock.py -q
```

## Conventions

- Prefer **behavior** names (`test_production_rejects_short_secret`) over ticket IDs.
- Production contracts live in `security/test_production_0_1_lock.py` — do not weaken.
- Soft deps (`ux_dom`, `opentelemetry`, `redis`) stay optional; tests skip or soft-import.
