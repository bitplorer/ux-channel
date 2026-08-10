# Soak test harness — design

## Goal

Prove **uxchannel WebRTC + channel** stay healthy under sustained concurrent
use with production-shaped doors (tickets, optional Redis), and emit a
**pass/fail report** against SLOs — not a one-shot unit test.

## What we soak (planes)

| Plane | Endpoints | Failure modes under load |
|-------|-----------|---------------------------|
| Actions | `POST /ux-channel/action` | Latency, 429/503, cap errors |
| RTC HTTP | `GET/POST /ux-channel/rtc` | Room full, ticket deny, inbox lag |
| RTC WS | `WS /ux-channel/rtc/ws` | Connect storm, drop, reconnect |
| Metrics | `GET /ux-channel/rtc/metrics` | Counter monotonicity |
| Store | Memory or Redis | Cross-worker signal delivery |

## Architecture

```text
                    ┌─────────────────────┐
                    │  Soak CLI (harness) │
                    │  scenarios + SLOs   │
                    └─────────┬───────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
    ┌────────────┐    ┌────────────┐    ┌────────────────┐
    │ Driver A   │    │ Driver B   │    │  SLO Reporter  │
    │ actions    │    │ rtc mesh   │    │  JSON + text   │
    └─────┬──────┘    └─────┬──────┘    └───────▲────────┘
          │                 │                   │
          └────────────┬────┴───────────────────┘
                       ▼
              ┌─────────────────┐
              │ Target process  │  in-process TestClient
              │ or live base URL│  OR multi-worker uvicorn
              └────────┬────────┘
                       ▼
              Channel.boot + /rtc + optional Redis
```

### Modes

| Mode | When | How |
|------|------|-----|
| **`inline`** | CI / laptop | One process, `TestClient`, Memory or FakeRedis |
| **`http`** | Staging soak | Many threads → `BASE_URL` (you run 2+ workers) |
| **`spawn`** | Local multi-worker | Harness spawns `uvicorn` workers + Redis URL |

### Drivers (scenarios)

1. **`ticket_gate`** — no ticket → 403; valid ticket → 200  
2. **`rtc_mesh`** — N peers poll + offer/answer/ice/ice-done exchange  
3. **`rtc_ws`** — WS hello + signal fanout + optional reconnect  
4. **`action_mix`** — concurrent signed actions (regression under RTC load)  
5. **`metrics_slo`** — metrics endpoint up; counters non-decreasing  
6. **`redis_cross`** *(http/spawn + REDIS_URL)* — peer A worker1, peer B worker2  

### SLOs (defaults — overridable)

| Metric | Default SLO |
|--------|-------------|
| Action success rate | ≥ 99% |
| RTC poll success (authed) | ≥ 99% |
| Ticket deny rate (unauthed) | = 100% of unauthed probes |
| p95 RTC poll latency | ≤ 200 ms (inline) / ≤ 500 ms (http) |
| p95 action latency | ≤ 100 ms (inline) / ≤ 300 ms (http) |
| WS hello success | ≥ 98% |
| Room-full handled | 409 not 5xx |
| Metrics scrape | 200 always |

Pass = all enabled scenarios meet SLOs. Fail = any breach (exit code 1).

## Threats / chaos (optional flags)

* **`--chaos-stale-ticket`** — expired tickets must 403  
* **`--chaos-room-full`** — max_peers overflow → 409  
* **`--chaos-ws-drop`** — close mid-session; client path recovers via poll  
* **`--duration 60`** — sustained loop instead of fixed request count  

## Report artifact

```json
{
  "ok": false,
  "mode": "inline",
  "duration_s": 12.4,
  "scenarios": {
    "ticket_gate": {"ok": true, "denies": 100, "allows": 100},
    "rtc_mesh": {"ok": true, "p95_ms": 42, "success_rate": 0.997},
    "action_mix": {"ok": false, "success_rate": 0.98, "slo": 0.99}
  },
  "metrics_end": {"counters": {"signals_total": 1200}}
}
```

Written to ``--report path.json`` (default ``soak-report.json``).

## Non-goals

* Browser WebRTC media quality (use Playwright later)  
* Real TURN path validation (infra; harness only checks ICE *signaling*)  
* Replacing unit tests  

## Runbook

```bash
# CI / local fast
python scripts/soak/harness.py --mode inline --duration 15

# Staging
export BASE_URL=https://staging.example
export SOAK_SECRET=...
python scripts/soak/harness.py --mode http --duration 120 --peers 16

# Local multi-worker (Redis required)
export REDIS_URL=redis://127.0.0.1:6379/0
python scripts/soak/harness.py --mode spawn --workers 2 --duration 60
```

## Code map

| File | Role |
|------|------|
| `docs/production/SOAK.md` | This design |
| `scripts/soak/harness.py` | CLI entry |
| `scripts/soak/app_factory.py` | Minimal Channel app under test |
| `scripts/soak/scenarios.py` | Drivers |
| `scripts/soak/report.py` | SLO aggregation |
| `scripts/soak/target.py` | inline / http / spawn adapters |

## Exit codes

* `0` — all SLOs green  
* `1` — SLO breach or scenario error  
* `2` — misconfiguration (no BASE_URL in http mode, etc.)

## Verified runs (local)

| Mode | Result | Notes |
|------|--------|--------|
| `inline` | PASS | CI / TestClient |
| `http` | PASS | Live uvicorn, tickets + mesh + WS + actions |
| `spawn` | PASS | Harness boots its own uvicorn |
| `http --duration 15` | PASS | Sustained multi-round |

Redis multi-worker: set `REDIS_URL` when Redis is available.
