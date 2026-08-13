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
