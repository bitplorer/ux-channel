## 2026-08-13 — Docs polish (names + maps)

- One speech: `HostRuntime` / `PeerApply` / `PeerRuntime` / classic `Peer` gate
- README, ARCHITECTURE, NAMING, REFERENCE, rust crate blurb updated
- Inventory + arch vectors already in `verify.sh`

---

## 2026-08-13 — Finish remaining architecture gaps

- SPEC: budgets, concurrency, codecs, profiles, inventory, non-goals
- CI vectors: `conformance/vectors/arch/*` + `validate_arch_vectors.py` (verify.sh)
- web.v1 complete (push_url, reload, focus, set_text); trace.v1 + wire.v1 drivers
- project() drops morph/navigate when only agent.v1 is claimed
- Host emit rejects over-budget graphs; JS apply verifies effect proofs when configured
- PeerApply single-flight tests; HostRuntime.handle_json adapter

---

## 2026-08-13 — Rust host kernel + host runtime

- `HostRuntime` (`rust/src/host.rs`): sessions, hello, `handle_intent`, project, proofs, flow correlation, health
- Host kernel modules: `effects`, `project`, `registry`, `stamps`, `flow` (same law as Python `arch/`)
- Peer kernel/runtime kept (`PeerApply` / `PeerRuntime`); classic `Peer` gate unchanged
- Classic floor: no hello → flattened toast ops; Cap key ≠ proof key; flow_id is not authority

---

## 2026-08-13 — Rust peer kernel + peer runtime

- `rust/src/apply.rs` — `PeerApply` (proofs, single-flight, budgets, seq / invoke / timer). No DOM.
- `rust/src/runtime.rs` — `PeerRuntime` hello / `submit_intent` / on_result / revoke; `Loopback` joins gate + runtime; `Outbox` opt-in
- `rust/src/proof.rs` — HMAC-SHA256 effect proofs (Python-compatible body hash)
- `rust/src/drivers.rs` — web.v1 / agent.v1 log packs + `safe_href`
- Python `PeerRuntime.submit_intent` + optional outbox/transport (SPEC `runtime-peer.md`)
- SPEC `runtime-peer.md` / `runtime-host.md` landed in `SPEC/architecture/`

---

## 2026-08-13 — Architecture polish (stability + clarity)

- Shared `arch.modes` tokens; HostConfig rejects unknown effects/proofs/flow
- Channel.boot installs MemoryNonceStore in development / allow_memory_stores (once/jti actually consumes)
- ArchRegistry isolates handler exceptions (`internal`, zero ops)
- PeerApply uses a real lock; budget/proof rejects recorded on `ctx["reject"]`
- Timer body applies through the kernel (`apply_ops` / `ctx.apply_ops`)
- Proofs use integer unix `exp`; fail closed if `proofs=require` without a key
- FlowStore missing/closed ids raise `FlowError`; store has a max-row cap
- Hello maps accept only profiles/features/effect_proof; Channel.revoke_session bumps gen
- Rust jti mixes secret + clock + pid (not a time-only hash)
- MemoryNonceStore evicts lazily instead of scanning every consume

---

## 2026-08-13 — Architecture merge (IR 0.1 floor preserved)

- Cap once/jti consume in Python `CapService.verify` (atomic, fail-closed) and Rust `mint_once` + `MemoryNonceStore`
- present-cap-must-verify already on both peers; inspect path uses `consume_once=False`
- `ux_channel.arch`: EffectGraph, project(auto|classic), proofs, stamps, FlowStore, HostRuntime, PeerApply
- Channel power attach: `emit_graph` / `set_hello` / `grant_stamp` (not public API)
- JS: seq / timer.set / timer.clear / invoke + `peerHello`; `static/ux-peer-kernel.js` (no DOM)
- RedisNonceStore SET NX EX fail-closed; config `UX_CHANNEL_EFFECTS/PROOFS/FLOW/PROOF_SECRET`
- SPEC/architecture ADRs 0001–0007; gate `test_arch_e2e.py`
- Health `once_jti_enforced: true`

---

## 2026-08-11 — Deeper hardening (post-seal)

- cap.sub wins over soft principal from Intent.args when they disagree
- Security events for role-claim probes, principal mismatch, rate limits, agent confirm denials
- Production defaults: `ws_require_origin=True`; navigate hosts derived from `allowed_origins`
- Tests updated: client-supplied roles no longer authorize (use `principal=Principal.of(..., roles=...)`)
- Expanded `tests/gate/test_deeper_hardening.py`

## 2026-08-11 — Automation default + freshness + package design overviews

- **Default:** ceremonial code is automated; hand-code only when extending features or making law/public-API changes ([AUTOMATION.md](AUTOMATION.md))
- Catalog regen mirrors `package_docs` + `strata`; layout soft-skips import smoke if host deps missing
- Package `__init__.py` Design / Architecture / Implementation overviews on core packages
- Fix stale [python/MERGE.md](python/MERGE.md) (no `zones`/shims as current truth); rewrite [python/CONTRIBUTING.md](python/CONTRIBUTING.md)
- AGENTS.md aligned with automation-first checklist

## 2026-08-11 — Production hardening (connector push)

- Soft principal id-only; meta/regions/flow no client roles
- roles_of principal-only; agent confirm requires signed secret
- MCP session store max_sessions fail-closed
- Rate + idempotency fail-closed (already on main)
- WebRTC ticket/origin defaults fail-closed; asyncio hygiene

**Note:** Full file bodies for registry/regions/flow/runner/sessions/config are pushed via GitHub API connector (MCP OAuth). Shell `git push` cannot see that token.

---

## 2026-08-11 — CI green: msgpack for CXB goldens + test path fixes

- requirements-dev: msgpack + hypothesis (CXB oracle decode needs msgpack)
- Harden CXB `_free_loads` error when msgpack missing
- Fix ops imports and monorepo paths in core tests

---

## 2026-08-11 — Rust/Python tests: unit, property, integration + docs

- Rust: proptest cap/wire properties; integration_peer; README layout/tests
- Python: gate cap properties (Hypothesis); integration Channel dispatch
- TESTING.md; verify runs cargo test --lib --tests
