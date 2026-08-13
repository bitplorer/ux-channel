# Testing — Python host + Rust crate

**Goal:** unit, property, and integration coverage without folklore.  
**CI entry:** `./verify.sh` (layout, longevity, vectors, gate, `cargo test`, `uxc_check`).

---

## Quick commands

```bash
# Full monorepo
./verify.sh

# Python — gate (freeze + cap properties)
export PYTHONPATH="$PWD/python/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m pytest python/tests/gate -q

# Python — integration (Channel mint → dispatch)
python3 -m pytest python/tests/integration -q

# Python — property (cap + architecture; needs hypothesis)
python3 -m pytest python/tests/gate/test_cap_properties.py python/tests/gate/test_arch_properties.py -q

# Python — architecture coverage floor
python3 -m pytest python/tests/gate -q --cov=ux_channel.arch --cov-fail-under=80

# Rust — unit + property + integration
cd rust && cargo test --lib --tests && cd ..

# Conformance (shared law)
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

---

## Cap law (both languages must hold)

1. `hash_args` = SHA-256 of sorted compact JSON → 32 hex chars  
2. mint(action, args) → verify(token, action, args) succeeds  
3. Different action or args → verify fails  
4. Oracle vector: `{"sku":"abc-123","qty":2}` → `96e4f83e3793b646323a67f314b51044`

---

## Anti-bloat for tests

* Gate tests stay **fast** and freeze public surface / longevity  
* Property tests assert **invariants**, not huge fixtures  
* Integration tests hit **real Channel/Peer**, not mocks of the protocol  
* Demo UI (`uxc_peer` HTML) is not the test oracle — vectors are  

See also: [LONGEVITY.md](LONGEVITY.md) · [rust/README.md](rust/README.md) · [START_HERE.md](START_HERE.md)
