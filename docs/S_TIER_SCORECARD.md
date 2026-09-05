# S-tier scorecard — ux-channel

Read [START_HERE.md](../START_HERE.md) first if you are new.

HEAD: `ux-channel` @ current `main` · `cek-python` **0.1.3**.
Critic is independent of the author of each loop.

North star:

```text
Intent {action, args, cap} → verify → action → Result {ok, ops[]} → client apply
```

---

## Critic verdict (latest)

| Loop | Date | Verdict | Notes |
|------|------|---------|-------|
| 0 | 2026-08-15 | **FAIL** (baseline) | Scorecard only. |
| 1 | 2026-08-15 | **SHIP** | Planes ≥ 4. |
| 2 | 2026-08-16 | **SHIP** | Readable `channel.py`. `async_dispatch` law. cek-host 0.1.3. Docs pyramid. |

SHIP requires every plane ≥ 4, no kill-criteria, `make verify` / gate green.

---

## Planes after loop 2

| # | Plane | Score | Notes |
|---|-------|------:|-------|
| 1 | First 5 minutes | **4** | README one screen. START_HERE 5-minute box + async/cek. |
| 2 | Doc pyramid | **4** | L0 README+START_HERE. L1 MENTAL_MODEL/FREEZE/TESTING. Stale root md in `docs/archive/`. |
| 3 | Explain / CLI | **4** | unchanged |
| 4 | Scaffold | **4** | unchanged |
| 5 | Security | **4** | unchanged |
| 6 | Kernel honesty (cek) | **4** | `[cek]` ≥ 0.1.3. `CekHostCapService` wraps `Host`. Default require (cut #3). `async_verify`. |
| 7 | Test honesty | **4** | `test_async_dispatch.py` + A≡B + D4. |
| 8 | Flagship | **4** | unchanged |
| 9 | Operability | **4** | unchanged |
| 10 | Power preserved | **5** | `@on` + classic dict Intent. |
| 11 | Classic IR 0.1 | **5** | no hello / no CXB still dispatches. |
| 12 | Layer honesty (D4) | **5** | `cek_surface` ↛ `ux_channel`. No vendor-copy. |

Phase 2 delete-clone of native enhance is **not** started (`off` keeps the clone).

### Dual API (locked)

| Call | `def` | `async def` |
|------|-------|-------------|
| `dispatch` / `submit` | runs | refused |
| `async_dispatch` / `async_submit` | runs | awaits |

`dispatch_async` is an alias of `async_dispatch`.
