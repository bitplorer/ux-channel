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
