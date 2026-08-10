# Placement — one source of truth (no HTML in channel)

## Principle

**uxchannel never owns the document.** It returns structured **Placement** data.
ux-dom / Jinja / any UI turns that into tags.

```text
Channel  →  Placement { attrs, client, scripts[] }
ux-dom    →  <script>, <body attrs>, <video>…
demo.py  →  optional HTML strings for scaffolds/tests only
```

## Day-1

| API | Returns |
|-----|---------|
| `ch.control(action)` | `ControlAttrs` (dict via `.as_dict()`) |
| `ch.runtime()` | `Placement` (script URLs) |
| `ch.media.plugin(...)` | `MediaPlugin` → attrs/client/scripts |
| `ch.bridge.mount_spec(...)` | `Placement` for widget host |
| `ch.bridge.mount_ops(...)` | Result ops |

## Not day-1 (demo / power)

| Avoid as truth | Instead |
|----------------|---------|
| `ch.scripts()` HTML | `ch.runtime().scripts` |
| `p.scripts_html` | `demo.script_tags(p)` |
| `ch.button` / `ch.page` | ux-dom + control |
| `ch.webrtc.*` teaching | `ch.media.plugin` |
| `ch.bridge.media` | **removed** — `ch.media` |

## Example (product)

```python
p = ch.media.plugin(room, sub=user_id)
rt = ch.runtime(webrtc=False)  # if media scripts already cover

# ux-dom (illustrative)
Document(
  head=[Script(src=s.src, defer=s.defer) for s in (*rt.scripts, *p.scripts)],
  body_attrs=p.attrs,
)
# join with p.client / p.client_json
```

## Example (demo only)

```python
from ux_channel.paint.demo import script_tags, attr_string, demo_page
html_head = script_tags(p)
```
