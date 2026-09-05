# Testing — Python host + Rust crate

Read [START_HERE.md](START_HERE.md) first if you are new.

**Goal:** unit, property, and integration coverage without folklore.  
**CI entry:** `./verify.sh` (layout, longevity, vectors, gate, `cargo test`, `uxc_check`).

---

## Green means

| Command | Green means | Not this |
|---------|-------------|----------|
| `make verify` | health + layout + longevity + law vectors + **gate** + rust + `uxc_check` | not the full 332+ pytest suite; not soak |
| `make verify-sec` | pentest + extreme_hardening (CI on main, **separate job**) | not inside the default gate |
| `make verify-http` | verify + live peer + demo forward | flaky ports; RC only |
| `pytest python/tests/gate` | freeze, cap oracle, enhance, **async_dispatch**, cek honesty (default decide = cek-runtime Host) | not ASGI/stress |
| `pytest python/tests/security` | residuals (morph policy, memory stores, href) | not soak |
| `uxchannel doctor --fail` | SECURITY_AUDIT deploy checklist is GO | a pretty JSON dump |
| `uxchannel upgrade-check . --fail` | no `require_cap=False` / open `/sfu/token` / raw `ChannelConfig(` | a suggestion |
| `uxchannel create-app /tmp/x` | generated app compiles; README teaches doctor | “files exist” |

Soak stays `make verify-http` / the soak job. **Do not put soak in `make verify`.**

---

## Quick commands

```bash
# Full monorepo (the contract)
make verify

# Security residuals (CI on main, not the default gate)
make verify-sec

# Python — gate (freeze + cap properties + cek honesty)
export PYTHONPATH="$PWD/python/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m pytest python/tests/gate -q

# Python — security residuals
python3 -m pytest python/tests/security -q

# CEK Phase 1 (optional extra)
python3 -m pytest python/tests/gate/test_async_dispatch.py python/tests/gate/test_cek_dropin_parity.py python/tests/gate/test_cek_layer_honesty.py -q

# Python — integration (Channel mint → dispatch)
python3 -m pytest python/tests/integration -q

# Architecture coverage floor
python3 -m pytest python/tests/gate -q --cov=ux_channel.arch --cov-fail-under=80

# Rust
cd rust && cargo test --lib --tests && cd ..

# Conformance
cd rust && cargo run --bin uxc_check -- ../conformance && cd ..
```

---

## What each layer covers

| Layer | Python | Rust |
|-------|--------|------|
| **Unit** | `tests/core`, `tests/gate` (incl. `test_arch_e2e.py`) | `cap`, `host`, `apply`, `project`, `peer`, `cxb` |
| **Property** | Hypothesis: `test_cap_properties.py`, `test_arch_properties.py`, `tests/core/test_wire_properties.py`, `tests/foundations/test_properties.py` | proptest: `cap`, `wire_json`, `project`, `proof`, `apply` |
| **Coverage** | `pytest --cov=ux_channel.arch --cov-fail-under=80` (in `./verify.sh`) | `cargo test --lib` exercises kernel/runtime modules |
| **Integration** | `tests/integration/test_channel_dispatch.py` | `tests/integration_peer.rs` |
| **Conformance** | `conformance/harness/` + `vectors/arch/` | `uxc_check` + `tests/arch_vectors.rs` |
| **CEK drop-in** | `test_cek_dropin_parity.py`, `test_cek_layer_honesty.py`, `test_async_dispatch.py` | — |
| **Security** | `tests/security/` via `make verify-sec` | — |

---

## Cap law (both languages must hold)

1. `hash_args` = SHA-256 of sorted compact JSON → 32 hex chars  
2. mint(action, args) → verify(token, action, args) succeeds  
3. Different action or args → verify fails  
4. Oracle vector: `{"sku":"abc-123","qty":2}` → `96e4f83e3793b646323a67f314b51044`

---

## Perf honesty

Do not claim a CXB / p95 number that is not in
[`python/docs/core/WIRE_BENCH.md`](python/docs/core/WIRE_BENCH.md)
(from `scripts/bench_wire.py`). Measured on this tree: html_heavy CXB is **15× denser**
than JSON (143 B vs 2145 B) and **not always faster** on encode (json orjson p50
~0.007 ms vs cxb ~0.019 ms). Classic JSON path must not regress >10% because of
the cek adapter — prove with `test_cek_dropin_parity` + a bench rerun, not folklore.

---

## Anti-bloat for tests

* Gate tests stay **fast** and freeze public surface / longevity  
* Property tests assert **invariants**, not huge fixtures  
* Integration tests hit **real Channel/Peer**, not mocks of the protocol  
* Demo UI (`uxc_peer` HTML) is not the test oracle — vectors are  
* Soak is never the default gate  

See also: [LONGEVITY.md](LONGEVITY.md) · [rust/README.md](rust/README.md) · [START_HERE.md](START_HERE.md) · [docs/S_TIER_SCORECARD.md](docs/S_TIER_SCORECARD.md)
