# Hardening status

Connector push path confirmed from agent workspace.

Pending on main (local ready under /tmp/uxc + /home/workdir/artifacts/hardening-push):

- host/registry.py — soft principal id-only, meta without client roles
- host/regions.py, host/flow.py — no client roles into scope
- agent_runtime/runner.py — confirm requires signed secret
- mcp/sessions.py — max_sessions fail-closed
- host/config.py — webrtc ticket/origin fail-closed defaults

Already on main: rate limit, idempotency, roles_of, changelog notes.
