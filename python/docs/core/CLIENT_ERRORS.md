# Client error handling (ux-channel.js 0.1)

## Goals

1. One path for **protocol**, **network**, **validation**, **refresh**, and **op** failures.
2. Apps can observe everything without re-implementing fetch.
3. Stock UX (toasts / field highlights) is optional and non-duplicating.

## Events

| Event | When | `detail` |
|-------|------|----------|
| `uid:beforeApply` | Before ops | `{ result, preventApply, source }` — set `preventApply=true` to cancel |
| `uid:applyCancelled` | Cancelled apply | same |
| `uid:error` | Any `reportError` / failed Result | `{ result, error, kind, source, entry }` |
| `uid:fieldErrors` | `error.fields` painted | `{ fields }` |
| `uid:refreshErrors` | `meta.refresh_errors` | `{ result, errors, source }` |
| `uid:opError` | Single op threw | `{ op, index, error, result }` |
| `uid:networkError` | fetch timeout / offline | `{ error, message, result }` |
| `uid:afterApply` / `uid:applied` | After ops | result |
| `uid:push` / `uid:pushError` | SSE | topic / reason |
| `uid:wsError` | WebSocket | reason / code |

Kinds on `uid:error.kind`: `protocol` · `validation` · `refresh` · `network` · `op` · `transport` · `unknown`.

## API

```js
// Listen (returns off())
const off = uxChannel.on("uid:error", (d) => {
  console.log(d.kind, d.error, d.entry);
});

// Configure
uxChannel.configure({
  autoToast: true,           // stock error toasts
  toastRefreshErrors: false, // toast partial refresh_errors
  fieldErrors: true,         // paint error.fields
  logSize: 40,
  dedupeMs: 2500,            // identical toast dedupe window
});

// Debug / support
uxChannel.lastErrors(20);
uxChannel.clearErrorLog();
uxChannel.reportError("custom", { message: "…", toast: true });

// Field helpers
uxChannel.applyFieldErrors({ email: ["Required"] });
uxChannel.clearFieldErrors();
```

## Body attributes

```html
<body
  data-channel-endpoint="/ux-channel/action"
  data-channel-dev
  data-channel-auto-toast="0"
  data-channel-toast-refresh-errors
  data-channel-field-errors="1"
  data-channel-error-log="50"
>
```

## Field errors (server)

```python
return Result.failure(
    "validation",
    "Fix the form",
    fields={"email": ["Required"], "qty": ["Must be ≥ 1"]},
)
```

```html
<input name="email" />
<span data-channel-error="email" hidden></span>
```

Client sets `aria-invalid`, `.ux-field-error`, and `role="alert"` on the message node.

## Network / HTTP

| Condition | Behavior |
|-----------|----------|
| Timeout / offline | Synthetic `Result` (`timeout`/`network`), `uid:networkError`, toast once, `err.handled` |
| Non-JSON 4xx/5xx | Synthetic failure → applyResult |
| 502/503/504 | One automatic retry |
| 429 | Warning toast + body apply |

## Op isolation

If one op throws (bad selector, bridge crash), remaining ops still run; `uid:opError` fires; toast only in **dev**.

## Cancel apply

```js
uxChannel.on("uid:beforeApply", (d) => {
  if (d.result.meta && d.result.meta.skip_client) d.preventApply = true;
});
```

## SSE / WS

Same `applyResult(result, { source })` path. Transport blips → `uid:pushError` / `uid:wsError`. Queue overflow on server drops **oldest** (prefer fresh morphs).

## Recommended app pattern

```js
uxChannel.configure({ autoToast: false }); // use design-system toasts

uxChannel.on("uid:error", ({ kind, error, entry }) => {
  if (kind === "validation") return; // fields already painted
  app.toast.error(error.message);
  if (entry.retryable) app.showRetry();
});

uxChannel.on("uid:refreshErrors", ({ errors }) => {
  app.metrics.increment("uid.refresh_errors", errors.length);
});
```
