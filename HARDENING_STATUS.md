# Hardening status

## On main (connector pushes)
- Fail-closed rate limit + idempotency
- roles_of principal-only
- MCP sessions max_sessions fail-closed (b1a1fa0)
- HARDENING_STATUS notes

## Pending connector upload (local ready)
- agent_runtime/runner.py — confirm fail-closed
- host/registry.py — soft principal id-only
- host/regions.py, host/flow.py — no client roles
- host/config.py — webrtc fail-closed defaults
