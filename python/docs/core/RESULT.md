# Intent & Result — uxchannel 0.1

Wire protocol version field: **`"v": "1"`**.

## Intent

| Field | Role |
|-------|------|
| `uid` | Protocol major (`"1"`) |
| `action` | Dotted action name |
| `args` | JSON object |
| `cap` | Capability token (required when `require_cap`) |
| `target` | Optional morph hint |
| `request_id` | Correlation |
| `form` | Progressive enhancement fields (do not override sealed trust) |
| `idempotency_key` | Optional dedupe |

## Result

| Field | Role |
|-------|------|
| `ok` | Success flag |
| `ops` | Ordered apply list |
| `error` | `{code, message, fields?}` when not ok |
| `meta` | `action`, `duration_ms`, `runtime`, … |

## Common ops

| `op` | Purpose |
|------|---------|
| `morph` | Patch DOM at `target` with `html` |
| `toast` | User message |
| `navigate` / `push_url` | Navigation (unsafe schemes stripped) |
| `swap` | outerHTML-style swap |
| `bridge.*` | npm bridge lifecycle |
| `noop` | Dropped / no-op |

Schema file: [uid-result.schema.json](uid-result.schema.json).


## Refresh errors (0.1)

| Case | Result |
|------|--------|
| All uids missing/crash, no notice | `ok=false`, `error.code=render_error`, `meta.refresh_errors` |
| All fail **with** notice | `ok=false`, same error, ops include **warning** toast (not a false success) |
| Partial fail | `ok=true`, morph survivors, `meta.refresh_errors` |
| `go=` after failed refresh | Failure **preserved** (navigate op may still be present; client skips navigate on `ok=false`) |

### Client hooks (`ux-channel.js`)

```js
uxChannel.on("uid:error", ({ result, error }) => { ... });
uxChannel.on("uid:refreshErrors", ({ errors, result }) => { ... });
uxChannel.on("uid:pushError", (d) => { ... });  // SSE transport / bad JSON
uxChannel.on("uid:wsError", (d) => { ... });
// also: uid:beforeApply, uid:afterApply, uid:applied, uid:push
```

See also [CLIENT_ERRORS.md](CLIENT_ERRORS.md) for the browser error plane.

## Batch envelope

See [ERRORS.md — Batch envelope status](ERRORS.md#batch-envelope-status).
