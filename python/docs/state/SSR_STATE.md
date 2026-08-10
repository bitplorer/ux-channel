# ssr_state

Server UI locals → region re-paint. Simple by default; **namespace** when you have many.

## Application

```python
ui = ssr_state(ch)
n = ui.session("n", 0)

@ui.region
def badge(ctx):
    return f"<b>{n()}</b>"

@ui.action
def inc():
    n.add(1)

button("+", **ui.bind(inc))
```

Same key → same local (shared on purpose).

## Many cells — `namespace` only

Do **not** put N row counters in one page-level local. Namespace them:

```python
row = ui.namespace("line", line_id)
qty = row.session("qty", 0)     # key: line:{id}:qty · feeds row.uid by default

@row.region                  # region uid = line:{id}
def view(ctx):
    return f"{qty()}"

# paint
row.paint()
```

| API | Role |
|-----|------|
| `ui.namespace(*parts)` | isolated key prefix |
| `row.session(name, default)` | cell under prefix; **feeds `row.uid` by default** |
| `row.session(..., feed=False)` | no auto feed |
| `@row.region` | register region at `row.uid` |
| `row.paint()` | SSR that region |
| `row.namespace(...)` | nest further |

There is no `item` / `ns` — only **`namespace`**.

## Power

```python
n = ui.session("n", 0, refresh="badge")
n.map(lambda x: x * 2)
with ui.changes():
    a.add(1); b.add(1)
```

## Rules

1. Page chrome → `ui.session`  
2. N widgets / rows → `ui.namespace`  
3. Prefer `add` / `map` / `toggle` / `merge`  
4. Auto-track on paint; namespace locals auto-feed their `uid`

## Example

`examples/ssr_state`
