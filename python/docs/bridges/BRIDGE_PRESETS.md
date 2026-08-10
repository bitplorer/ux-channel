# Bridge presets — factory default + contract-driven props

## Application

```python
charts = ChartBridge(ch)
rev = charts("revenue", values=[12, 19], kind="bar")
return rev.commit(values=[4, 9, 14])
```

Generated presets use the **same** shape; kwargs come from **`contract.json` → `mount_props`**.

## Where do parameters come from?

```text
npm package real API
        ↓  (catalog or hand-edited)
contract.json  mount_props.properties
        ↓  codegen
preset.py  MOUNT_PROP_KEYS + docs + widgets('id', type=…, options=…)
```

We **do not invent** `css=` (or any field) unless it appears in `mount_props`.

| Package | Example mount_props (real fields) |
|---------|-------------------------------------|
| chart.js | `type`, `data` / `labels` / `datasets`, `options`, `title` |
| leaflet | `center`, `zoom`, `layers`, `options` |
| codemirror | `value`, `language`, `theme`, `extensions` |

Chart.js has **no** top-level `css` prop. Styling it supports goes under **`options`** (plugins, layout, …). That is why codegen exposes `options`, not a fake `css=`.

## Host element styling (ux-dom)

Classes / CSS variables on the **wrapper** are ux-dom’s job:

```python
spec = rev.mount_spec()
# host: Div(className="h-80", style="…", **spec.attrs_py)
```

Optional low-level Placement helpers on `ch.bridge.mount_spec(..., class_name=, style=)` exist for demos — they are **not** package props.

## Extend props for a package

Edit `bridges/<name>/contract.json`:

```json
"mount_props": {
  "type": "object",
  "properties": {
    "options": { "type": "object", "description": "Chart.js options" },
    "plugins": { "type": "array", "description": "if your adapter maps it" }
  }
}
```

Re-run or regenerate preset so `MOUNT_PROP_KEYS` / docs update.

## Commands

```bash
uxchannel bridge catalog
uxchannel bridge preset chartjs --out bridges
uxchannel create-app myapp --bridge chartjs
```


## Methods: names + parameters from contract

| Contract field | Codegen |
|----------------|---------|
| `methods.setView.args` | `def set_view(self, center, zoom=None)` |
| method name camelCase | Python snake_case |
| `w.set_view(...)` | `ch.done` Result + `bridge.call` |
| `w.set_view_ops(...)` | ops list only |

```bash
# enrich args (then re-run preset, or edit contract.json)
uxchannel bridge add-method leaflet setView --arg center:array:required --arg zoom:number
uxchannel bridge preset leaflet --out bridges --force
```

```python
w = LeafletBridge(ch)("map1", center=[28.6, 77.2], zoom=12)
return w.set_view([28.7, 77.1], 14)   # args from contract
```

Generic escape: `w.call("setView", center, zoom)` / `w.commit_call(...)`.

## Stunning UI effects (ux-fx)

Self-contained adapters in ``/ux-channel/static/adapters/ux-fx.js`` (after ``ux-bridge.js``).

| Bridge | Package | Effect |
|--------|---------|--------|
| `ConfettiBridge` | `ux-fx/confetti` | Celebration bursts / cannon / rain |
| `ParticlesBridge` | `ux-fx/particles` | Interactive particle field |
| `AuroraBridge` | `ux-fx/aurora` | Mesh gradient / aurora background |
| `CountUpBridge` | `ux-fx/countup` | Animated metrics |
| `SpotlightBridge` | `ux-fx/spotlight` | Pointer glass spotlight |
| `LottieBridge` | `lottie-web` | Lottie JSON (CDN loader) |

```python
from ux_channel.bridges import ConfettiBridge, CountUpBridge, ParticlesBridge, AuroraBridge
from ux_channel.render.kit import fx_script_tags

confetti = ConfettiBridge(ch)
return confetti("win", theme="neon").burst()

metrics = CountUpBridge(ch)
return metrics("mrr", value=12840, prefix="$").commit(value=14200)
```

Demo host scripts: ``fx_script_tags()``. Example: ``examples/fx_showcase``.

## High-value UI libraries (host islands)

Imperative islands only — **not** a ShadCN/design-system replacement. Host chrome stays in the host.

| Bridge | Package | Adapter | Use |
|--------|---------|---------|-----|
| `LeafletBridge` | leaflet | ux-ui.js | Maps |
| `CodeMirrorBridge` | codemirror | ux-ui.js | Code editors |
| `SelectBridge` | tom-select | ux-ui.js | Searchable select |
| `DatePickerBridge` | flatpickr | ux-ui.js | Dates |
| `SortableBridge` | sortablejs | ux-ui.js | Drag-and-drop lists |
| `SwiperBridge` | swiper | ux-ui.js | Carousels |
| `MermaidBridge` | mermaid | ux-ui.js | Diagrams |
| `QuillBridge` | quill | ux-ui.js | Rich text |
| `GenericBridge` | *any* | your adapter | Escape hatch |

```python
from ux_channel.bridges import LeafletBridge, SelectBridge, GenericBridge
from ux_channel.render.kit import bridge_script_tags

maps = LeafletBridge(ch)
hq = maps("hq", center=[28.6, 77.2], zoom=11)
# host: Div(**hq.mount_attrs(class_name="h-80 rounded-xl overflow-hidden"))

widgets = GenericBridge(ch, package="my-lib", methods=("update", "destroy"))
return widgets("x", theme="dark").commit(theme="light")
```

Scripts: ``bridge_script_tags()`` (ux-bridge + fx + ui), or ``ui_script_tags()`` / ``fx_script_tags()``.
