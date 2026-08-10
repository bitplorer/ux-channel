# Server error mapping (uxchannel 0.1)

## Contract

Every action response is a **Result**:

```json
{ "ok": false, "ops": [], "error": { "code": "validation", "message": "…", "fields": {}, "retryable": false }, "meta": { … } }
```

HTTP status is a **secondary** signal for caches/proxies/browsers.  
**Clients must branch on `ok` / `error.code`, not only status.**

Source of truth: [`ux_channel/error_map.py`](../src/ux_channel/error_map.py).

## Code → HTTP status

| Code | HTTP | Kind | Default retryable |
|------|------|------|-------------------|
| `unauthorized` | 401 | auth | no |
| `forbidden` | 403 | auth | no |
| `confirmation_required` | 403 | auth | no |
| `bad_request` | 400 | protocol | no |
| `validation` | 422 | validation | no |
| `not_found` | 404 | protocol | no |
| `payload_too_large` | 413 | protocol | no |
| `upgrade_required` | 426 | protocol | no |
| `conflict` | 409 | protocol | no |
| `rate_limited` | 429 | network | **yes** |
| `timeout` | 504 | network | **yes** |
| `unavailable` | 503 | network | **yes** |
| `render_error` | 500 | refresh | **yes** |
| `internal` | 500 | protocol | no |
| `encode_error` | 500 | protocol | no |
| `not_implemented` | 501 | protocol | no |
| *(unknown)* | **422** | protocol | no |

## Who emits what

| Layer | Typical codes |
|-------|----------------|
| Preflight (origin, header, rate, size) | `forbidden`, `payload_too_large`, `rate_limited`, `upgrade_required` |
| Cap / auth | `unauthorized` |
| Registry (unknown action, bad args) | `not_found`, `bad_request` |
| Action `raise ActionError` / `ch.fail.*` | `validation`, `forbidden`, … |
| Region paint total failure | `render_error` |
| Handler crash | `internal` |
| Encode / limits | `encode_error`, `payload_too_large` |
| Timeout | `timeout` |

## Product API (`ch.fail`)

```python
return ch.fail.auth()                    # unauthorized
return ch.fail.forbidden()
return ch.fail.rate()                    # rate_limited
return ch.fail.valid(fields, region=…, html=…)  # validation + morph
return ch.fail.code("conflict", "Already paid")
```

```python
raise ActionError("validation", "Bad email", fields={"email": ["required"]})
```

## Meta enrichment (`ensure_error_meta`)

On every failed Result leaving `ActionRegistry._finalize` and host adapters:

| meta key | Meaning |
|----------|---------|
| `error_kind` | Client kind (`auth`, `validation`, `refresh`, …) |
| `http_status` | Status that hosts will use |
| `error.retryable` | Filled when code is in retryable set and was `null` |

## Hosts

| Host | Mapper |
|------|--------|
| FastAPI | `_status_for` → `http_status_for` |
| Starlette | `http_status_for` |
| Raw ASGI | `status_for` → `http_status_for` |

## Batch

Batch envelope uses `200` if merged `ok`, else **422** (individual items keep their own Result codes).

## Client alignment

Browser maps `error.code` → toast/kind in [CLIENT_ERRORS.md](CLIENT_ERRORS.md).  
Prefer `meta.error_kind` when present (server-authoritative).

```js
uxChannel.on("uid:error", ({ error, entry, result }) => {
  const kind = (result.meta && result.meta.error_kind) || entry.kind;
  ...
});
```

## Batch error code mapping

Per-item codes still use the **same** table as solo actions (`ERROR_HTTP_STATUS`).
The envelope **aggregates** them; it does not invent new codes.

### Mapping path

```text
batch[i].error.code
        │
        ▼
  http_status_for(item)     → item_statuses[i]
  kind_for_code(code)       → kind_counts
        │
        ▼
  Aggregate
    error_codes[]     codes in failure order
    item_codes[]      parallel to batch (null if ok)
    code_counts{}     frequency per code
    kind_counts{}     frequency per kind
    code_http{}       code → HTTP for codes present
    worst_code/kind   lowest severity among failures
        │
        ▼
  batch_http_status
    all_ok     → 200
    mixed      → 207  (HTTP does not pick a single error code)
    all_error  → ERROR_HTTP_STATUS[worst_code]  (via status severity)
    envelope   → single Result code (e.g. payload_too_large → 413)
```

### Example meta

```json
{
  "status_mode": "mixed",
  "http_status": 207,
  "item_statuses": [200, 422, 401],
  "item_codes": [null, "validation", "unauthorized"],
  "error_codes": ["validation", "unauthorized"],
  "code_counts": { "validation": 1, "unauthorized": 1 },
  "kind_counts": { "validation": 1, "auth": 1 },
  "code_http": { "validation": 422, "unauthorized": 401 },
  "worst_code": "unauthorized",
  "worst_kind": "auth"
}
```

On **mixed (207)** clients must not treat `worst_code` as “the” batch error —
apply each item. `worst_*` is for logging/metrics only.

On **all_error** the envelope HTTP status equals `code_http[worst_code]`
(severity order may prefer 401 over 422 even if validation appeared first).

### Severity (HTTP) used for worst

`500 → 504 → 503 → 501 → 429 → 401 → 403 → 413 → 409 → 404 → 400 → 426 → 422`

Ties: first failed item with that status wins.

### Diagnostics

```python
from ux_channel.protocol.error_map import map_batch_error_codes

summary = map_batch_error_codes(envelope)
# { status_mode, http_status, worst_code, code_counts, ... }
```

## Batch retry

Opt-in per-item retry for **retryable** failures only.

### Request flags (`POST /ux-channel/batch`)

| Field | Default | Meaning |
|-------|---------|---------|
| `retry_retryable` | `false` | Enable retries |
| `max_retries` | `1` | Extra attempts after the first (capped at 5) |
| `retry_backoff_ms` | `50` | Sleep between attempts |

### What is retryable?

Uses `item_is_retryable(Result)`:

1. `error.retryable is True` → yes  
2. `error.retryable is False` → no  
3. else → `should_retry(code)` (`rate_limited`, `timeout`, `unavailable`, `render_error`, …)

**Not** retried by default: `validation`, `unauthorized`, `forbidden`, …

### Response `meta.retry`

```json
{
  "enabled": true,
  "max_retries": 1,
  "backoff_ms": 50,
  "attempts": [1, 2],
  "retried_indices": [1],
  "recovered": 1,
  "exhausted": 0
}
```

| Field | Meaning |
|-------|---------|
| `attempts` | Dispatch count per returned item |
| `retried_indices` | Items that got at least one extra attempt |
| `recovered` | Failed then succeeded after retry |
| `exhausted` | Still retryable-fail after all attempts |

### Safety

- **Default off** — actions may not be idempotent.
- **Once-caps**: nonce is consumed on first verify; the same cap usually cannot be retried successfully. Sign a fresh cap or avoid once-caps for flaky batch items.
- `stop_on_error` runs **after** that item’s retry budget.
- Prefer retries for pure reads / refresh actions.

### Python

```python
from ux_channel.transport.batch import dispatch_batch, item_is_retryable

out = dispatch_batch(
    registry,
    items,
    retry_retryable=True,
    max_retries=2,
    retry_backoff_ms=25,
)
```

## Backoff strategies

Shared module: `ux_channel.backoff` (used by batch retry).

| Strategy | Formula (attempt = failures so far) | When |
|----------|-------------------------------------|------|
| `fixed` | `base_ms` | Default; simple 1–2 retries |
| `linear` | `base_ms * attempt` | Mild growth |
| `exponential` | `min(max, base * factor**(attempt-1))` | Server load, rate limits |
| `exponential_full_jitter` | `U(0, exp)` | **Best against thundering herd** |
| `exponential_equal_jitter` | `exp/2 + U(0, exp/2)` | Bounded + spread |

### Batch request fields

| Field | Default | Role |
|-------|---------|------|
| `retry_backoff_ms` | 50 | Base delay |
| `retry_backoff_max_ms` | 5000 | Cap |
| `retry_backoff_strategy` | `fixed` | See table |
| `retry_backoff_factor` | 2.0 | Exponential multiplier |

### Response `meta.retry.backoff` + `delays_ms`

```json
"retry": {
  "enabled": true,
  "max_retries": 3,
  "backoff": { "strategy": "exponential", "base_ms": 50, "max_ms": 5000, "factor": 2.0 },
  "backoff_ms": 50,
  "attempts": [4],
  "delays_ms": [[50, 100, 200]],
  "retried_indices": [0],
  "recovered": 0,
  "exhausted": 1
}
```

### Recommendations

| Context | Strategy |
|---------|----------|
| Batch max_retries ≤ 1 | `fixed` (default) |
| Rate limit / multi-tenant fan-in | `exponential_full_jitter` |
| Deterministic tests | `fixed` or `exponential` with `rng` seeded via `BackoffPolicy` |
| Client-side re-POST of failed items | Same policy; add jitter so tabs don’t align |

```python
from ux_channel.transport.backoff import BackoffPolicy, compute_backoff_ms

policy = BackoffPolicy(strategy="exponential_full_jitter", base_ms=50, max_ms=2000)
wait = policy.delay_ms(attempt=2)
```

## Retry-After override

When a failure carries **Retry-After** (HTTP header or `meta.retry_after` seconds),
batch backoff and clients treat it as a **minimum** wait (mode `max`, default).

### Sources (first hit)

1. `Result.meta.retry_after` / `retry_after_s`
2. `error.details.retry_after`
3. HTTP `Retry-After` header (delta-seconds or HTTP-date)

### Modes (`retry_after_mode`)

| Mode | Wait |
|------|------|
| `max` (default) | `max(computed_backoff_ms, retry_after_s * 1000)` |
| `replace` | `retry_after_s * 1000` only |
| `min` | `min(computed, ra_ms)` (rarely useful) |

### Producers

```python
return Result.failure("rate_limited", "slow down", retryable=True, retry_after=30)
# rate_limit_hook sets retry_after from token refill interval
# HTTP adapters default Retry-After: 5 header for 429 if meta omits it
```

### Batch

```python
dispatch_batch(..., retry_retryable=True, retry_after_mode="max")
# meta.retry.delay_details[i][j] =
#   { computed_ms, retry_after_s, wait_ms, override, strategy, mode }
```

### HTTP

`POST /ux-channel/action` and `/ux-channel/batch` set `Retry-After` from result meta when status is 429 (or any mapped failure that carries meta).

### Client

`ux-channel.js` merges the header into `result.meta.retry_after` and emits `uid:retryAfter`.
