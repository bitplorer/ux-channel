<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Enterprise live + suite pass (0.1)

Recorded verification after multi-JS / multi-region hardening.

## Automated suite

| Suite | Result |
|-------|--------|
| Full `pytest tests/` | **980 passed**, 1 skipped |
| Chaos / load / stress / pentest subset | **139 passed** |
| Security (HTTP/WS/push/WebRTC hardening) | **62 passed** |
| Consistency audit | **critical=0** |

## Load / stress scripts

| Script | Result |
|--------|--------|
| `scripts/load_test_channel.py` | 500/500 HTTP 200, ~230 rps, p95≈165ms |
| `scripts/enterprise_stress_pentest.py` | 1000/1000 HTTP 200; pentest OK (header/cap/href) |
| `scripts/io_channel_soak.py` | ok+fail intentional (scope denials); audit=200 |

## Live DOM (Playwright)

| Harness | Result |
|---------|--------|
| `js_live_chaos.mjs` | OK — CSRF, caps, concurrent clicks |
| `js_multi_live_chaos.mjs` | OK — all scripts, double-load, wrong-order |
| `js_enterprise_live.mjs` | OK — multi-region isolation, stress, bridges, reload |

Enterprise live highlights:

* Bump A does not change B/C; keep markers intact  
* Nested C note refresh isolated  
* 25 concurrent A clicks → A=26, B unchanged  
* Mixed concurrent A/B/all → consistent counters  
* Bridge instances `fx1`/`cu1` survive boom + morph  
* 3× reload → globals still present; empty console  

## Known non-goals of this pass

* Real peer WebRTC media (two browsers / cameras)  
* Every ux-ui CDN package mount (leaflet/quill/…) online  
* Multi-worker Redis production cluster soak  

Re-run::

```bash
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src python scripts/enterprise_stress_pentest.py
PYTHONPATH=src python scripts/load_test_channel.py
# live (start matching *_server.py first)
node scripts/js_enterprise_live.mjs http://127.0.0.1:8769
```
