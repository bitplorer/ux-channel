# Error handling examples

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |

## First principles

1. Every action outcome is a **Result** (`ok` + optional `error` + `ops`).
2. Failures still may **update UI** (re-morph the form, toast, focus).
3. **`error.code`** is stable; HTTP status is secondary (`error_map`).
4. Clients branch on `ok` / `error.code`, not status alone.
5. Prefer product speech: **`ch.fail.*`** over hand-rolled dicts.

Spec tables → [`docs/core/ERRORS.md`](../core/ERRORS.md)  
Runnable → `examples/error_handling/`

---

## 1. `Result.failure` (library core)

```python
from ux_channel.protocol.types import Result
from ux_channel.protocol.ops import morph, toast

return Result.failure(
    "validation",
    "Please fix the highlighted fields",
    morph("#login", form_html),
    toast("Invalid email", level="error"),
    fields={"email": ["required"]},
)
```

Retryable / throttle:

```python
return Result.failure(
    "rate_limited",
    "Too many requests",
    retryable=True,
    retry_after=30,  # Result.meta
)
```

---

## 2. `raise ActionError` (handler)

```python
from ux_channel.protocol.errors import ActionError

@reg.action("signup")
def signup(ctx, email: str = ""):
    if "@" not in email:
        raise ActionError(
            "validation",
            "Invalid email",
            fields={"email": ["required"]},
        )
    return Result.success()
```

Registry catches `ActionError` → `ok=false` Result (same codes as above).

---

## 3. Product speech — `ch.fail.*` (preferred)

| Call | Code | HTTP |
|------|------|------|
| `ch.fail.valid(fields, region=…, html=…)` | `validation` | 422 |
| `ch.fail.auth()` | `unauthorized` | 401 |
| `ch.fail.forbidden()` | `forbidden` | 403 |
| `ch.fail.rate()` | `rate_limited` | 429 |
| `ch.fail.code("conflict", "…")` | any stable code | mapped |

```python
@ch.on("transfer")
def transfer(ctx, amount: float = 0, balance: float = 0):
    if amount <= 0:
        return ch.fail.valid(
            {"amount": ["must be positive"]},
            region="Transfer:form",
            html=render_form(),
            message="Check amount",
            focus="#amount",
            notice=True,  # error toast
        )
    if amount > balance:
        return ch.fail.code("forbidden", "Insufficient funds")
    return ch.done(toast(f"sent {amount}"))
```

Also on `UiBuilder`:

```python
return ch.ui.toast("Nope", level="error").fail("forbidden", "Nope")
return ch.ui.fail_validation({"email": ["required"]}, region="Form:root", html=…)
```

---

## 4. Map to HTTP / client kind

```python
from ux_channel.protocol.error_map import ensure_error_meta, http_status_for

ensure_error_meta(result)
status = http_status_for(result)          # int
kind = result.meta.get("error_kind")      # auth | validation | network | …
```

| Code | HTTP | Kind | Default retryable |
|------|------|------|-------------------|
| `validation` | 422 | validation | no |
| `unauthorized` | 401 | auth | no |
| `forbidden` | 403 | auth | no |
| `rate_limited` | 429 | network | **yes** |
| `conflict` | 409 | protocol | no |
| `internal` | 500 | protocol | no |

---

## 5. DX / CLI errors

```python
from ux_channel.devtools.errors import DxUsageError, DxNotFoundError

raise DxUsageError("missing --out", hint="uxchannel dashboard --out reports/dx")
# exit_code=2, code=dx.usage
```

Never silent: CLI paths log `code` + `hint`.

---

## 6. What not to do

| Avoid | Prefer |
|-------|--------|
| Raise bare `Exception` for expected validation | `ActionError` / `ch.fail.valid` |
| Return HTML-only 400 with no Result | `Result` + ops |
| Invent HTTP status in handlers | Stable `error.code` + `error_map` |
| Put secrets in `error.details` / `meta` | Redact; observe-only digests |

---

## Run the suite

```bash
PYTHONPATH=src python examples/error_handling/run.py
```
