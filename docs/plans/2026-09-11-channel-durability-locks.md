---
title: Lock Channel Cap machine and HTTP claims
date: 2026-09-11
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

# Channel durability locks

## Goal Capsule

Close verified honesty and fail-closed gaps in ux-channel without changing the product idea (Intent → verify → Result ops) or the frozen public names.

ux-compose is a separate repo. This work owns Channel-side compose coupling (`ActionRegistry.from_config`, `apply_host_adapter`, `UXCOMPOSE_STATE_STORE`, HTTP health claims). Compose Isolation Law stays out of tree.

Stop when: `from_config` uses the same Cap machine as `Channel.boot`; HTTP `/action` is JSON-only and health says so; `[cek]` messaging matches required deps; auth resolver exceptions fail closed; factory configure errors are visible; tests lock each claim.

## Product Contract

### Requirements

- R1. `ActionRegistry.from_config(config)` with `config.cek != "off"` installs the same Cap adapter as `create_channel` / `Channel.boot` (cek-runtime Host on require).
- R2. `apply_host_adapter` is idempotent so factory + from_config cannot register `after_cek_cut2` twice or swap twice.
- R3. EffectGraph without a present cap is refused on the from_config path, not only `Channel.boot`.
- R4. Python HTTP `/action` and `/batch` accept JSON (and form) only. CXB Content-Type is `bad_request`. Responses are JSON unless HTML or SSE.
- R5. Python `/health` advertises `formats` (HTTP today) vs `codecs` (library) and policy flags, matching Rust peer honesty.
- R6. Error/doctor/explain copy must not claim `pip install 'ux-channel[cek]'` installs wrap packages. `cek-host` / `cek-surface` are required deps; `[cek]` is an empty alias.
- R7. `auth_resolver` exceptions fail closed with `unauthorized` and a security event. They must not become anonymous dispatch.
- R8. `create_channel` concurrency/wire configure failures log. Production re-raises.
- R9. `cek=adapt` stays a documented compare mode; a test locks that classic `CapService` remains authority.
- R10. Public frozen names (`Channel`, `Channel.boot`, `CapService`, `Intent`, `Result`, `apply_host_adapter` import path) do not change.

### Out of scope

- ux-compose Isolation Law (compose `wire/`).
- Removing `cek=adapt` or `cek=off`.
- Integer handler-binding coercion (`"2"` → `2` on annotated ints). Protocol/cap hash already uses raw args; form binding stays. Residual.
- Public API redesign, sibling packages, HTML/CSS ownership.

### Acceptance examples

- AE1. `ActionRegistry.from_config(ChannelConfig.development(...))` → `type(reg._caps).__name__ == "CekHostCapService"` and `after_cek_cut2` in after hooks.
- AE2. Same registry, handler returns `_graph` without cap → `ok is False`, ops empty.
- AE3. POST `/ux-channel/action` with `Content-Type: application/ux-channel+cxb` → 400.
- AE4. GET `/ux-channel/health` includes `formats: ["application/ux-channel+json"]` and `codecs` containing `json` and `cxb`.
- AE5. Resolver that raises → Result `unauthorized`; security bus has `auth_resolver_failed`.

## Planning Contract

### Key technical decisions

- KTD1. Wire CEK in `from_config`, not a new flag. Rejected: `install_cek=` default True (another door). Reason: config.cek already decides.
- KTD2. Make `apply_host_adapter` idempotent by mode + machine type + hook identity. Rejected: remove factory call. Reason: factory still covers the no-config env path.
- KTD3. Enforce HTTP JSON floor in `asgi/pipeline.py` preflight (shared FastAPI + Starlette). Rejected: advertise CXB on Python health because negotiation exists. Reason: law is JSON on HTTP; library CXB stays in `codecs`.
- KTD4. Always fail closed when `auth_resolver` raises. Rejected: fail only in production. Reason: exception is not "no user".
- KTD5. Keep empty `[cek]` extra as alias; fix lying copy. Rejected: move wrap packages back to optional extra. Reason: cut #3 / ADR 0010 already required them.

### Assumptions

- Compose that uses `from_config` + `apply_host_adapter` remains safe (idempotent).
- Compose that uses `from_config` alone currently has classic caps while config says require; this PR closes that. Follow-up: compose should rely on from_config, not a second adapter call.

### Sequencing

U1 adapter → U2 HTTP honesty → U3 auth/factory → U4 tests/docs.

## Implementation Units

### U1. from_config is the Cap door

Files: `python/src/ux_channel/host/registry.py`, `python/src/ux_channel/cek/host_adapter.py`, `python/src/ux_channel/LAYERS.md`

- Call `apply_host_adapter(reg, config)` at end of `from_config` when `parse_cek(config.cek) != "off"`.
- `apply_host_adapter`: if already applied for the same mode (require + CekHostCapService, or adapt + `_cek_caps`), return mode. Register `after_cek_cut2` only if not already in `registry.hooks.after`.
- LAYERS.md: from_config applies the frozen adapter; compose must not skip it.

Tests: `python/tests/gate/test_from_config_cek.py`, strengthen `python/tests/gate/test_longevity_strata.py` compose lock, `python/tests/gate/test_cek_adapt.py`.

### U2. HTTP JSON floor + health claims

Files: `python/src/ux_channel/asgi/pipeline.py`, `python/src/ux_channel/asgi/fastapi.py`, `python/src/ux_channel/asgi/starlette.py`

- Preflight rejects non-JSON/non-form Content-Type with `bad_request`.
- Action/batch encode JSON unless HTML/SSE.
- Shared `health_payload(registry, *, health_list, path)` with formats/codecs/http/policy.

Tests: `python/tests/asgi/test_fastapi_action.py`, `python/tests/foundations/test_further_111.py` (preflight CXB).

### U3. Fail-closed auth + visible factory errors + cek copy

Files: `python/src/ux_channel/host/registry.py`, `python/src/ux_channel/host/factory.py`, `python/src/ux_channel/cek/config.py`, `python/src/ux_channel/cek/host_adapter.py`, `python/src/ux_channel/devtools/doctor.py`, `python/src/ux_channel/devtools/explain.py`, `python/pyproject.toml` comments, `PUBLIC_API_FREEZE.md` duplicate rows.

Tests: `python/tests/security/test_auth_resolver_fail_closed.py`, `python/tests/gate/test_cek_deps_honesty.py`, `python/tests/host/test_factory_configure_errors.py`.

### U4. Compose follow-up note (docs only in PR)

No compose code in this repo. PR lists follow-ups: Isolation Law; prefer from_config (adapter now included); do not set `UXCOMPOSE_STATE_STORE` and `REDIS_URL` ambiguously.

## Verification Contract

- `PYTHONPATH=python/src python3 -m pytest python/tests/gate/test_from_config_cek.py python/tests/gate/test_longevity_strata.py python/tests/gate/test_cek_adapt.py python/tests/gate/test_cek_deps_honesty.py python/tests/asgi/test_fastapi_action.py python/tests/foundations/test_further_111.py python/tests/security/test_auth_resolver_fail_closed.py python/tests/host/test_factory_configure_errors.py python/tests/gate/test_cek_layer_honesty.py python/tests/gate/test_cek_runtime_host.py python/tests/gate/test_public_api_freeze.py -q`
- `./verify.sh` (or `make verify`) before claiming green.

## Definition of Done

- R1–R10 evidenced by tests or explicit residual.
- No public rename.
- PR lists ux-channel improvements, compose/deps scope, residual risks, verify commands.
