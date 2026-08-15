<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Testing — ux-channel 0.1

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |

## Run the suite

```bash
cd ux-channel
PYTHONPATH=src python -m pytest tests/ -q
```

Layout and conventions: [`tests/README.md`](../../tests/README.md).

## What “green” means

| Band | Packages | Must hold |
|------|----------|-----------|
| Core wire | `core/`, `client/`, `asgi/` | Intent/Result, CSRF header, encode |
| UI plane | `regions/`, `bridges/` | Morph, bridge contracts |
| Production | `security/` | Caps on, no short secrets, surface brutal |
| Peer | `ux_dom_glue/` | Soft interop only |
| DX | `dx/` | Doctor, dashboard model schema **1** |

## Production lock (do not weaken)

```bash
PYTHONPATH=src python -m pytest tests/security/test_production_0_1_lock.py -q
```

## Live harness (optional)

```bash
PYTHONPATH=src python -m uvicorn examples.live_full_harness.app:app --host 0.0.0.0 --port 8090
```

See also: [PRODUCTION.md](../production/PRODUCTION.md) · [STACK.md](STACK.md).
