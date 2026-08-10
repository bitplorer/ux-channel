# DX guide — minimal cognitive load

## One-screen start

```bash
uxchannel dx                 # mental model + decision tree
uxchannel recipe --tree
uxchannel recipe counter
uxchannel create-app myapp
uxchannel doctor
```

```python
print(Channel.describe())
print(Channel.help())              # decision tree
print(Channel.help("aliases"))     # use this, not that
print(Channel.help("counter"))     # recipe
ch.doctor()                        # health + hints
```

## Application only (16 names)

`boot` · `on` · `region` · `control` · `scripts` · `body_attr_string` ·  
`draft` · `done` · `fail` · `refresh` · `sign` · `diagnose` ·  
`webrtc` · `media` · `config` · `path`

Everything else is a **layer** (import when needed).

## Decision tree

| Need | Use |
|------|-----|
| Click / form → server → morph | `@ch.on` + `ch.control` |
| Live fragment | `@ch.region` + `refresh=[…]` |
| 1:1 A/V | `ch.media.plugin(..., mode="mesh")` |
| Group A/V | LiveKit env + `mode="sfu"` |
| New project | `uxchannel create-app` |

## Prefer → not (aliases)

| Avoid (still works) | Prefer |
|---------------------|--------|
| `ch.webrtc.plugin` | `ch.media.plugin(..., mode="mesh")` |
| `ch.media.session` | `ch.media.plugin` |
| `ch.button` / `ch.page` | ux-dom + `ch.control` |
| Open `POST /sfu/token` | Server-side `ch.media.plugin(mode="sfu")` after auth |
| `ch.sign` alone | `ch.control(...).cap` when you need the string |

## Strict hygiene

```bash
export UX_CHANNEL_STRICT_DX=1   # warn on ch.button / ch.page
```

## Recipes

| Name | Intent |
|------|--------|
| `counter` | Region morph loop |
| `form` | Signed form |
| `media-mesh` | Mesh bag |
| `media-sfu` | LiveKit bag |
| `ux-dom-control` | ux-dom button attrs |
| `production` | Fail-closed config |

## Long-term stability rules

1. **Root API frozen** — application names only grow with a major version.
2. **No UI chrome in channel** — plugins are placement bags.
3. **One media façade** — `ch.media`; mesh/sfu are modes.
4. **Caps by default** — never ship `require_cap=False` to prod.
5. **Scaffold is the doc** — generated apps teach the pattern.
6. **Layers for power** — agents, whip, redis, otel stay import-only.

See [GOLDEN_PATH.md](../start/GOLDEN_PATH.md) · [MEDIA.md](../bridges/MEDIA.md) · [SCAFFOLD.md](SCAFFOLD.md) · [STANDARDS.md](../production/STANDARDS.md).


## Explain failures (teach, don’t just fail)

```python
r = ch.registry.dispatch(intent)  # or host action path
print(ch.explain(r))
# → teach, recipe, cli hint
```

Missing cap message includes: use ``ch.control(action).as_dict()``.

## upgrade-check (CI)

```bash
uxchannel upgrade-check . --fail
```

Flags: ``ch.button``, ``ch.page``, ``ch.webrtc.plugin``, raw ``ChannelConfig(``,
``require_cap=False``, open ``/sfu/token``.

## ControlAttrs IDE surface

```python
attrs = ch.control(add, trust_sku=sku)
attrs.as_dict()      # **kwargs
attrs.as_ux_dom()     # underscore keys
attrs.attr_string    # str form
attrs.cap            # token | None
attrs.action         # action name
```

## Demo HTML path (P2)

```python
from ux_channel.render.kit import demo_button, demo_page  # preferred
# ch.button / ch.page → DeprecationWarning (still work)
```

## Bridges vs media (npm)

See [BRIDGE_STRATEGY.md](../bridges/BRIDGE_STRATEGY.md).

* Widgets: ``ch.bridge.host`` + ``packages/@ux-channel/…``
* Media: ``ch.media.plugin`` + app ``npm i livekit-client``
* Protocol JS only in ``src/ux_channel/static/``

## CLI logging (never silent)

See `ux_channel.dx_log` / `ux_channel.dx_errors`.

See also [ARCHITECTURE.md](../foundations/ARCHITECTURE.md) for cohesion map.
