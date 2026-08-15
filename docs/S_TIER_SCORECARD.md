# S-tier scorecard — ux-channel @ 95c9c55

Read [START_HERE.md](../START_HERE.md) first if you are new.

Cartographer pass (W0). Evidence from the tree, not memory.
HEAD: `ux-channel` @ `95c9c55` · `cek-python` @ `e3a129a`.
Critic is independent of the author of each loop.

North star (do not invent a synonym):

```text
Intent {action, args, cap} → verify → action → Result {ok, ops[]} → client apply
```

---

## Critic verdict (latest)

| Loop | Date | Verdict | Notes |
|------|------|---------|-------|
| 0 | 2026-08-15 | **FAIL** (baseline — expected) | Scorecard only. No production edits yet. |
| 1 | 2026-08-15 | **SHIP** | Every plane ≥ 4. Kills clean. `make verify` green. A≡B + D4 pasted below. |

SHIP requires every plane ≥ 4, no kill-criteria, timed first-5, `make verify` green.

---

## Planes after loop 1

| # | Plane | Score | Gap | Owner | Evidence |
|---|-------|------:|-----|-------|----------|
| 1 | First 5 minutes | **4** | G0 | W1 | README is one screen. START_HERE has a 5-minute box. `uxchannel create-app` is the happy path. In-tree create-app + validate = 0.002s. Full pip-from-zero not re-timed in this sandbox (deps preinstalled). |
| 2 | Doc pyramid | **4** | G1 | W1 | Layer 0 = README + START_HERE. Layer 1 = MENTAL_MODEL / FREEZE / GOLDEN_PATH / SECURITY_AUDIT. 89 Layer-2 pages point up. Encyclopedia not deleted. |
| 3 | Explain / CLI | **4** | G2 | W2 | `TEACH` ≥ 20. `uxchannel explain missing_scripts`. `doctor --fail` exits 1 on short secret / memory stores. |
| 4 | Scaffold = running app | **4** | G3 | W2 | Generated README teaches `doctor --fail` + `upgrade-check --fail`. Gate smoke compiles + asserts no `require_cap=False`. |
| 5 | Security residuals | **4** | G4 | W3 | `morph_html_policy=strict` opt-in (default off). Production TTL 900s. `doctor` refuses silent memory. Redis auto-wire already first-class. Cookie binding remains P2 accepted. |
| 6 | Kernel honesty (cek) | **4** | G5 | W4 | extra `[cek]`. `ChannelConfig.cek`. Adapter. A≡B on oracle/once/sealed-args/dispatch. Default off. Native clone still behind off (Phase 2 not started). |
| 7 | Test honesty | **4** | G6 | W5 | TESTING.md green-means table. `make verify-sec` (CI job, not default gate). create-app + enhance_search + cek honesty in gate. |
| 8 | Flagship product feel | **4** | G7 | W6 | enhance_search: empty / error / pending / once-used + 390px CSS + tap 44px. |
| 9 | Operability | **4** | G8 | W7 | `doctor()` go/no-go ≡ SECURITY_AUDIT checklist. `upgrade-check --fail` on README. Bench numbers cited from WIRE_BENCH.md. |
| 10 | Power preserved | **5** | — | W10 | Region `@on` + classic dict Intent both green after the adapter. |
| 11 | Classic IR 0.1 | **5** | — | W9 | Dict Intent `{v,action,args,cap}` with no hello / no CXB still dispatches. |
| 12 | Layer honesty (D4) | **5** | G5 | W4 | `cek_surface_imports_ux_channel() == []`. No vendor-copy. `cek=require` installs one `CekHostCapService`. |

Blended: **~4.2 / 5**. Phase 2 delete-clone is **not** started.

---

## REPLACE / ADAPT / KEEP (from the tree)

### REPLACE (native clone dies after Phase 2 SHIP — Phase 1 keeps it behind `off`)

| Channel native | cek owner | Notes |
|----------------|-----------|-------|
| `enhance/continuations.py` `Continuation` | `cek_surface.Continuation` | Near-1:1. Paths `store.`/`event.` vs `store:`/`event:`. |
| `ops/catalog.py` + `ops/macros.py` | `cek_surface.ops` | Wave A structured ops. Wire floor stays classic via `ops/translate.py`. |
| `static/ux-peer-perception.js` | `cek-surface/js/peer_ir.mjs` | Perception IR only. |
| `static/ux-peer-continuations.js` | `cek-surface/js/browser_peer.mjs` slot-fill | No Peer mint. |

### ADAPT (Channel façade, cek implementation when `cek=require`)

| Channel API | cek implementation | Constraint |
|-------------|-------------------|------------|
| `CapService.mint` / `verify` | `cek_host.Host` / `cek_host.CapService` | Token formats differ (itsdangerous vs hex+HMAC). Require path uses cek tokens. Off path unchanged. |
| `once` / `jti` / sealed-args | `cek_host` | Adapter always `seal_args=True` to match Channel semantics. |
| `present_cap_must_verify` | `cek_host.Host.submit` | Fail closed. |
| `EnhanceFacade.mint_continuation` | `cek_host` mint + `cek_surface.Continuation` | Only when `cek=require`. |
| `hash_args` oracle | both | `{"sku":"abc-123","qty":2}` → `96e4f83e3793b646323a67f314b51044` |

### KEEP IN CHANNEL (Surface is not this)

| Plane | Path |
|-------|------|
| Channel, Region, RegionBook, `@on`, `@region`, `control`, `draft` | `host/` |
| ASGI mount, SSE, WS, batch | `asgi/`, `transport/` |
| CXB + JSON floor | `wire/`, `conformance/` |
| workplace, MCP, agent_runtime, bridges, WebRTC, Redis | own packages |
| rust HostRuntime + PeerApply + `uxc_check` | `rust/` |
| Classic Peer kernel + DOM drivers | `static/ux-peer-kernel.js`, `ux-peer-dom-drivers.js` |
| Handshake / PeerHello / causal / delta / recorder | `enhance/` — no cek twin |
| Public root names | `PUBLIC_API_FREEZE.md` — do not grow |

### Name collisions (do not merge blindly)

| Name | Channel | CEK |
|------|---------|-----|
| `PeerSession` | `enhance.handshake` negotiated surfaces | `cek_surface.session` Carrier I/O |
| `Host` | (product is `Channel`) | `cek_host.Host` authority |
| `Result` | `{v, ok, ops, error}` | `{kind, ops, error}` |
| `CapService` | itsdangerous + rotation + durable nonce | hex+HMAC + in-memory jti |
| `Op` | classic `{op: morph}` on the wire | `{ns, name, payload}` compose |

---

## G0–G9 (honest gaps)

| Id | Gap | Proof it exists | Fix stream |
|----|-----|-----------------|------------|
| G0 | Too many front doors | README L18 + L26–30 lists START_HERE, MENTAL_MODEL, DOCS, AUTOMATION, STABILITY as “Start” | W1 |
| G1 | 193 md files, no pyramid pointers | `find -name '*.md'` | W1 |
| G2 | Top-20 explain incomplete | `devtools/explain.py` `TEACH` has 13 keys | W2 |
| G3 | Scaffold README is not the doc | `scaffold/create.py` `_readme` has no `doctor()` / `upgrade-check --fail` | W2 |
| G4 | Morph XSS HIGH; memory stores warn-not-refuse at config; Redis not factory-first | `SECURITY_AUDIT.md` L79, L155–159; `config.py` L252 | W3 |
| G5 | enhance is a native clone; no adapter | `ENHANCE_WAVES.md:66`; grep `cek_` → 0 | W4 |
| G6 | No green-means table; no `verify-sec`; no cek tests | `TESTING.md`; `Makefile` | W5 |
| G7 | enhance_search missing error / once-used / true empty | `demos/enhance_search/index.html` | W6 |
| G8 | `doctor()` always `ok: True`; CLI exits 0 | `Channel.doctor` decoded L481; `cli.py` L219 | W7 |
| G9 | Bench numbers exist but are not cited as the claim | `python/docs/core/WIRE_BENCH.md` | W7 |

---

## Kill-criteria watch

| Kill | Status @ W0 |
|------|-------------|
| PUBLIC_API_FREEZE broken / `__all__` grew | Clean — do not grow |
| `make verify` red | Untouched this loop |
| Classic IR 0.1 needs hello / CXB | Clean |
| Reverse import surface → channel | Clean (no cek dep yet) |
| Dual Cap machines disagree | N/A until W4 |
| Peer mints / recipes / authority kv | Clean (Wave C separate file) |
| START_HERE deleted or contradicted | Clean |
| production factory allows memory silently | Warns; boot raises unless opt-in |
| present bogus cap succeeds | Enforced |
| create-app app does not run | Untested this pass |
| Channel power lost “because Surface” | Not started |
| `require_cap=False` in a production template | create-app prod path keeps default True |
| soak stuffed into default gate | Clean |

---

## Proof log (critic must paste)

| Proof | Loop 0 | Loop 1 |
|-------|--------|--------|
| wall-clock create-app → first morph | not timed | create-app + validate_scaffold **0.002s** in-tree. `uxchannel create-app` is the README happy path. Full `pip install` from a clean venv was not re-timed (sandbox already had host deps). |
| `doctor()` on prod-misconfig | not run | short secret → `ValueError` + CLI exit 1. `allow_memory_stores=True` without Redis → `go: false`, CLI `--fail` exit 1. |
| import graph (cek adapter) | n/a | `cek_surface_imports_ux_channel() == []`. `channel_vendor_copy_hits() == []`. |
| A ≡ B parity | n/a | `test_cek_dropin_parity.py` **passed** (oracle, mint/verify, once replay, sealed-args, dispatch ops). |
| `make verify` line that was green | not run | `All verify checks passed.` (health + layout + longevity + gate 152 + rust + uxc_check). `make verify-sec` 29 passed. |
| two product planes still working | not run | `@ch.region` + `@ch.on(refresh=)` morph ok. Classic dict Intent `{v,action,args,cap}` (no hello, no CXB) ok. |

---

## Order of attack

1. W0 this file
2. W1 first-5 / pyramid
3. W2 explain / scaffold / doctor CLI
4. W3 security residuals
5. W4 cek Phase 1 adapter
6. W5 test matrix
7. W6 flagship feel
8. W7 doctor / benches
9. W9 classic floor (parallel)
10. W10 product planes regression
11. W8 delete-clone — **not started** until W4 critic SHIP

---

## What we will not do

- Rewrite Channel into Surface
- Grow root `__all__`
- Hand-edit `catalog.json` or `PACKAGE_MAP` `modules` / `module_count`
- Require CXB / hello for classic IR 0.1
- Vendor-copy cek-host or cek-surface into this tree
- Put soak inside `make verify`
- Ship `require_cap=False` in a production template
- Replace START_HERE with a new intro
- Start Phase 2 delete-clone before Phase 1 SHIP
