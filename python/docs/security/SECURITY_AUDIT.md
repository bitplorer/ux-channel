<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Security audit summary — uxchannel 0.1

**Scope:** server-driven UI channel (Intent → Action → Result/ops), caps, ASGI hosts, hooks, drafts/state, regions, agent/MCP surfaces.  
**Method:** static review + adversarial unit/HTTP pentests + chaotic concurrency apps (sandbox).  
**Status:** control plane hardened for 0.1; residual risks are mostly **app-owned** (HTML, redirects, multi-worker stores).

---

## Executive summary

| Area | Verdict |
|------|---------|
| Capability tokens (action + args hash) | **Strong** when `require_cap=True` + long secret |
| CSRF (browser JSON POST) | **Strong** in production (`X-UID-Channel` + origin rules) |
| Dangerous navigate schemes | **Blocked** (`javascript:`, `data:`, `//…`, etc.) |
| Auth / roles on actions | **Fixed** — `auth=True` honors `dispatch(principal=…)` via ContextVar |
| Async hooks on sync dispatch | **Fixed** — await when no event loop (no crash / dropped coro) |
| Rate limit / once-caps | **OK** in-process; **multi-worker needs Redis** |
| Morph HTML / toast content | **App must escape** — library does not HTML-sanitize fragments |
| Absolute `https://` navigations | **Allowed** — open-redirect policy is app-owned |

**Bottom line:** Safe to ship interactive UIs behind production config **if** morph HTML is escaped, secrets are strong, and multi-worker deploys use shared nonce/rate/state stores.

---

## Control matrix

| Control | Default (prod) | What it stops | Tests / notes |
|---------|----------------|---------------|---------------|
| **HMAC capabilities** | `require_cap=True` | Forged actions, arg tampering | Cap mismatch → `unauthorized` |
| **Sealed trust args** | Cap args hash | Client override of server-sealed fields | Form cannot override sealed `title` |
| **Once-caps + nonce** | optional `once=True` | Replay of one-shot buttons | Concurrent once → single winner |
| **Channel header** | `require_channel_header=True` | Naive CSRF on JSON POST | Missing header → 403 |
| **Origin allowlist / same-origin** | `enforce_same_origin=True` | Cross-site browser POSTs | Evil origin → 403; `Origin: null` denied |
| **`safe_href` + finalize sanitize** | always | `javascript:` / `data:` / protocol-relative navigations | Dropped to `noop` |
| **Action name validation** | always | Log injection, path-like names, overlong IDs | Max 128; dotted identifiers |
| **Body / batch size limits** | config | Request DoS | Batch 50 → 413/422 payload |
| **Action timeout** | `action_timeout_s` | Hung async/sync handlers | Timeout → `timeout` |
| **Internal error messages** | prod hides detail | Exception leakage | No `password=…` in prod |
| **`auth=True` / roles** | opt-in | Unauthenticated / wrong-role actions | Principal via ContextVar |
| **Rate limiting** | config hooks | Flooding (per process) | Memory limiter; Redis for multi-worker |
| **Agent / MCP token** | required for agent routes | Open agent surface | Config validate fails closed |
| **Trace HTTP** | off / token in prod | PII leakage via inspector | Token required in production |

---

## Findings log (chronological severity)

### Fixed (library)

| Sev | Finding | Remediation |
|-----|---------|-------------|
| **HIGH** | `auth=True` / roles ignored `dispatch(principal=…)` under action timeout (handler runs in ThreadPool without ContextVars) | `contextvars.copy_context().run` in `_call_sync_handler`; `_principal_from_call` for roles |
| **MED** | `navigate("javascript:…")` raised → action `internal` error | Soft-drop to `noop` op |

### Fixed (library) — prior

| Sev | Finding | Remediation |
|-----|---------|-------------|
| **CRITICAL** | Async `@ch.on` handlers registered as sync wrappers → coroutine dropped, empty success | Preserve `async def` through flow + `RegionBook.command` |
| **HIGH** | `auth=True` ignored `dispatch(principal=…)` when handler had no `principal` param | `_auth_wrap` reads `_principal_override` ContextVar + `Principal.id` |
| **HIGH** | `javascript:` / `data:` / `//` navigate ops (XSS / phishing) | `safe_href`, ops helpers, Result finalize sanitize |
| **HIGH** | Async before/after hooks crashed or leaked coroutines on sync dispatch | `asyncio.run` when no running loop |
| **HIGH** | MCP / agent open without token in bad configs | Always require agent token; prod validate |
| **MED** | CSRF: JSON POST without custom header | `require_channel_header` (prod default True) |
| **MED** | Weak capability secrets | Min length on `CapService` |
| **MED** | `Origin: null` accepted | Denied |
| **MED** | Unknown region refresh → action `internal` KeyError | Soft-skip missing / failed paints |
| **MED** | After-hook `return None` wiped `Result` | Ignore non-`Result`; keep prior result |
| **MED** | Draft `get`+`set` RMW races under concurrency | `edit` / `change` / `merge` (+ `async with edit`) |
| **LOW** | Empty morph/swap target | Reject empty CSS selector |
| **LOW** | Region multi-instance action name clash (`Class.method`) | Wire names `{uid}.{method}`; digit segments allowed |
| **LOW** | `diagnose()` duplicate `regions` key | Deduped; expose `action_endpoint` |

### Residual / accepted

| Sev | Risk | Owner | Mitigation |
|-----|------|-------|------------|
| **HIGH** | **Morph / toast XSS** if user strings embedded raw | App + lib | **Mitigated (opt-in)** — `morph_html_policy="strict"` strips script/on*/javascript: hrefs. Default **off** so ux-dom is not broken. `doctor()` warns when off in production. Tests: `tests/security/test_morph_policy.py`. |
| **MED** | **Open redirect** via `https://evil.example` navigate | App | Allowlist hosts before `navigate()` / encode `Go` |
| **MED** | **Stolen `data-channel-cap`** until expiry | App + lib | Short TTL, HTTPS, `bind_cap_to_principal`, `once` for money actions |
| **MED** | **Multi-worker** once/idempotency/rate/state | Deploy | Redis (or equivalent); do not use memory stores in multi-worker prod |
| **MED** | **`trusted_proxy` + XFF spoof** | Deploy | Only behind proxy that overwrites `X-Forwarded-For` |
| **LOW** | Missing `Origin` allowed | By design | Pair with channel header in prod |
| **LOW** | Agent prompt injection | App | Allowlist tools, confirm secrets, budgets |
| **INFO** | Absolute http(s) navigations not host-restricted | Policy | App policy layer |

---

## Threat model (short)

```text
Browser / agent
    │  Intent + cap (+ form)
    ▼
ASGI host ── origin + channel header + body limits
    ▼
Capability verify ── action name + args hash (+ once/nonce) (+ optional sub)
    ▼
before hooks ── rate limit, custom deny
    ▼
Action handler ── auth/roles, timeout, encode Result
    ▼
after hooks + sanitize_op_hrefs + size limits
    ▼
Client apply ops ── morph / toast / navigate (dangerous schemes already stripped)
```

**Trust boundaries**

1. **Browser is hostile** for args — only sealed trust + server loaders are truth.  
2. **Caps are bearer tokens** — protect with HTTPS, TTL, principal binding.  
3. **HTML in morph ops is trusted by the client** — server must escape.  
4. **Memory stores are process-local** — not a security domain across workers.

---

## Production deploy checklist

- [ ] `ChannelConfig.production(secret=…)` with **≥ 32-byte** random secret (`UX_CHANNEL_SECRET`)
- [ ] `require_cap=True` (default) — never disable in public prod
- [ ] `require_channel_header=True` (default)
- [ ] Set `allowed_origins` to real site origins (or rely on same-origin + correct Host)
- [ ] HTTPS only in front of the app
- [ ] Escape **all** user-controlled strings in region HTML / notices
- [ ] Validate navigate targets if absolute URLs are used
- [ ] Multi-worker: Redis (or shared) for nonce, idempotency, rate limit, state
- [ ] `once=True` + shared nonce for payments / irreversible actions
- [ ] Prefer `bind_cap_to_principal=True` for logged-in mutations
- [ ] Agent/MCP: token + confirm secret + explicit allowlist
- [ ] Trace / inspector off or token-gated; no payload capture in prod
- [ ] Never `trusted_proxy=True` without edge XFF rewrite
- [ ] Run `pytest` security suites in CI (`test_security_pentest`, enterprise pentest, chaos)

---

## Regression tests (security-relevant)

| Suite | Covers |
|-------|--------|
| `tests/security/test_security_pentest.py` | caps secret, href, origin, header, action names |
| `tests/stress/test_enterprise_stress_pentest.py` / `test_enterprise_brutal.py` | HTTP pen, load edges |
| `tests/asgi/test_auth_and_async_hooks.py` | `auth=True` + principal; async hooks |
| `tests/asgi/test_async_on_and_timeout.py` | async actions actually run; timeouts |
| `tests/state/test_draft_rmw.py` | RMW / CAS `edit` |
| `tests/stress/test_chaos_audit.py` | multi-instance, form sealed args, prod leak |
| `tests/security/test_extreme_hardening.py` | once-cap, sanitize, Go/javascript |

CI expectation: **gate green** (`make verify`). Security residuals: **`make verify-sec`** (not inside the default gate). Full suite remains available as `pytest tests -o testpaths=tests`.

---

## Recommended next hardening (post-0.1)

1. ~~Optional **HTML sanitizer policy** for morph (strict mode) without breaking ux-dom.~~ **Done (opt-in)** — `ChannelConfig.morph_html_policy = "strict"`. Default off; doctor warns.  
2. ~~**Navigate host allowlist** config.~~ **Done** — `navigate_allowed_hosts` + production derives from `allowed_origins`.  
3. Cap **binding to session cookie** / CSRF double-submit beyond custom header.  
4. ~~First-class **Redis** rate limit + nonce in default production factory.~~ **Done** — `REDIS_URL` auto-wires nonce/rate/idempotency/push; `production()` default TTL 900s; `doctor --fail` refuses silent memory stores.  
5. ~~Structured **security event** log stream~~ **Done** — bus + emitters for cap/origin/CSRF/rate/role claim/agent confirm/WS.  
6. Cap session binding (`bind_cap_to_principal=True` as production default when auth is always on). Recipe: `bind_cap_to_principal=True` on production config.

---



---

## Server-Sent Events (SSE push) — summary

Full write-up: **[SSE.md](../asgi/SSE.md)** (issues · bottom line · solutions).

| Risk | 0.1 status | Operator solution |
|------|------------|-------------------|
| Open subscribe | **prod fail-closed** + `public.*` | Private: ticket or `push_token` |
| Tickets | `ch.sign_push` / `?ticket=` | Bind topic (+ optional sub) |
| Global token ≠ user ACL | No per-topic principal | Tickets / opaque topics / edge auth |
| `?token=` leakage | EventSource limitation | Short TTL, Referrer-Policy, scrub logs |
| XSS via morph | App must escape | Escape in region renderers |
| Multi-worker miss | Memory bus per process | Redis push bus |
| DoS streams | Queue 64 | Edge connection limits; small morphs |

**Bottom line:** SSE is a **Result transport**, not action-level auth. Use for live read-only morphs; protect private topics; escape HTML; mutations stay on `POST /action`.

## Document history

| Ver | Notes |
|-----|--------|
| 0.1.0 | Initial adversarial pass (href, CSRF header, MCP token, secrets) |
| 0.1.x | ContextVar principal/request; once fail-closed; push token |
| **0.1 (this summary)** | Auth ContextVar fix; async hooks; async `@ch.on`; region multi-instance; draft `edit` CAS; refresh soft-fail; consolidated matrix |

*Last reviewed against sandbox chaotic/pen runs and library sources under `src/ux_channel/`.*

## WebSocket

Full write-up: **[WEBSOCKET.md](../asgi/WEBSOCKET.md)**.

| Risk | Control |
|------|---------|
| Unauth connect | Same as SSE fail-closed + tickets/token |
| Cross-site WS | Origin check (`allowed_origins` / same-origin) |
| Private subscribe | Per-message topic authorize |
| Intent without cap | Registry still verifies capabilities |
| Disabled | `ws_enabled=False` |
