# ux stack — channel ↔ dom

### Brand lines (do not mix)

| Package | PyPI / pip | Import | CLI |
|---------|------------|--------|-----|
| **ux-channel** | `ux-channel` | `ux_channel` | **`uxchannel`** |
| **ux-dom** | `ux-dom` | `ux_dom` | **`uxdom`** |
| Glue | ships with channel | `ux_channel_ux_dom` | — |

## Who owns what

```text
ux-dom                          ux-channel
────────                        ──────────
Document / Component            Intent → Action → Result(ops)
XElement + x_element.js         caps · morph · bridges · regions
DirectoryRouter / SSR           /ux-channel/action  +  /ux-channel/static/*
CSP · SafeStaticFile            CSRF header X-Channel
```

## Synergies (clean composition)

| Concern | Owner | Peer |
|---------|-------|------|
| Full page HTML | **ux-dom** `Document` | channel injects scripts via `ch.scripts()` or `UxChannelRuntime` |
| Live morph / signed actions | **ux-channel** | dom stamps `data-channel-*` via `ch.control(...).as_ux_dom()` |
| Custom elements | **ux-dom** `XElement` | independent of channel |
| Widget islands (Chart.js…) | **ux-channel** bridges + `uxBridge` | host element built in dom |
| CSRF | channel header **always**; host meta **optional** | `ux_channel_ux_dom` helpers |
| Static JS | **one copy** in site-packages | never dual-copy into app assets |

## Glue only (`ux_channel_ux_dom`)

```python
from ux_channel_ux_dom import control_ux_dom, paint_ux_dom_region, ux_dom_csrf_meta
```

Core packages never hard-import each other.

## Naming traps

| Name | Is | Is not |
|------|-----|--------|
| `ux_dom.runtime.Channel` | Document plugin (`UxChannelRuntime`) | `ux_channel.Channel` |
| `/ux-channel` | Default channel HTTP mount | Package name |
| `as_ux_dom()` | Kwargs for dom tags (`data_channel_*`) | A separate product |

## Install

```bash
pip install ux-dom ux-channel
```

## Testing

Each package owns its suite; glue tests live under **ux-channel** `tests/ux_dom_glue/`.

## Public conventions (0.1 — no private-looking wire)

| Layer | Convention | Notes |
|-------|------------|--------|
| PyPI | `ux-channel` / `ux-dom` | distribution names |
| Import | `ux_channel` / `ux_dom` | underscores |
| CLI | `uxchannel` / `uxdom` | unhyphenated |
| Env | `UX_CHANNEL_*` | secrets, path override |
| **HTTP mount (channel)** | **`/ux-channel`** | public control plane — **not** `/__…__` dunders |
| **HTTP static (dom)** | **`/ux-dom/static`** | package JS only |
| **data attrs** | **`data-channel-*`** / **`data-dom-*`** | owner in the name |
| **CSRF header** | **`X-Channel: 1`** | channel protocol (host CSRF separate) |
| JS global | `uxBridge` | bridge helper |
| Override path | `UX_CHANNEL_PATH` / `config.path` | never hardcode in app HTML |

### Why not `/ux-channel`?

Double-underscore paths read as **private/internal**. The browser only ever needs **public** URLs:

```html
<body data-channel-endpoint="/ux-channel/action">
<script src="/ux-channel/static/ux-channel.js" defer>
```

Set endpoint via ``ch.body_attrs()`` / ``demo_scripts(ch)`` so apps do not invent paths.

