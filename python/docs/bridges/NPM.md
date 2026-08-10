# npm package strategy (ux-channel)

## Bridging is **not** removed

Placement-first redesign removed **HTML generation** from the channel core.  
It did **not** remove npm bridging.

| Still works | Role |
|-------------|------|
| `ux-bridge.js` | Client island registry (`uxBridge.register`) |
| `bridge.mount` / `update` / `call` / `destroy` | Result ops |
| `BridgeManifest` + hub | Server allowlist for methods |
| `ch.bridge.mount_spec` | Placement data for host element |
| `ch.bridge.mount_ops`… | Emit ops |
| `packages/@ux-channel/*` | Optional published adapters |

```text
App template (ux-dom)          uxchannel Browser
─────────────────          ──────────────                 ─────────
host element attrs    ←──  ch.bridge.mount_spec
  data-channel-bridge-*
scripts               ←──  ch.runtime()  (includes ux-bridge.js)
Result ops            ←──  ch.bridge.mount_ops(...)   →   ux-bridge.js
                                                      →   adapter from npm
```

## Three layers of JS (do not mix)

| Layer | Location | Versioned with | Examples |
|-------|----------|----------------|----------|
| **Protocol** | `src/ux_channel/static/` | Python `uxchannel` | `ux-channel.js`, `ux-bridge.js` |
| **Widget adapters** | `packages/@ux-channel/*` or app `npm` | Own semver / app | chart, maps, editors |
| **Media SDKs** | app `npm` peerDeps | App only | `livekit-client` |

**Rule:** Protocol stays in the wheel. Feature npm packages stay in **npm** (workspace or app). Channel mints **ops + placement data**, never vendors Chart.js / LiveKit.

## Dedicated package management

### Monorepo (this repo)

```text
package.json                 # workspaces root
packages/
  @ux-channel/
    bridge-core/             # defineAdapter() helper
    media-livekit/           # peerDep livekit-client (media plane, NOT bridge ops)
    adapter-chartjs/         # optional future widget adapters
```

```bash
# from repo root
npm install
npm -w @ux-channel/bridge-core pack   # when publishing
```

### App project (production)

```bash
# protocol scripts still from Python static mount
# adapters from npm:
npm i chart.js
# optional:
npm i @ux-channel/bridge-core
```

Register adapter in **your** bundle:

```js
import { defineAdapter } from '@ux-channel/bridge-core';
import { Chart } from 'chart.js';

defineAdapter('chartjs', {
  mount(el, props) { /* new Chart(el, props) */ return instance; },
  update(inst, props) { /* ... */ },
  destroy(inst) { inst.destroy(); },
});
```

Server:

```python
from ux_channel.bridge_meta.bridge_api import register_simple_manifest

register_simple_manifest("chartjs", methods=("update", "destroy"))

@ch.on
def show_chart(ctx):
    spec = ch.bridge.mount_spec("sales", package="chartjs", props={"type": "bar", "data": ...})
    # ux-dom renders host from spec.attrs
    return ch.done(
        morph("#slot", host_html_from_spec(spec)),  # your markup
        *ch.bridge.mount_ops("sales", "chartjs", props=spec.client.get("props")),
    )
```

## Media is not an npm bridge package via `bridge.mount`

| | Widget bridge | Media |
|--|---------------|-------|
| API | `ch.bridge.*` | `ch.media.plugin` |
| Client | `uxBridge.register(name)` | LiveKit Room / mesh JS |
| Ops | `bridge.mount` | join / leave (client SDK) |
| npm | adapters + chart libs | `livekit-client` peerDep |

Using `bridge.mount("livekit")` is **wrong**. Use `ch.media.plugin` + `@ux-channel/media-livekit` or raw `livekit-client`.

## Publishing policy

1. **Python release** ships protocol static JS (semver with ux-channel).  
2. **`@ux-channel/*`** packages publish independently (or private registry).  
3. **App** pins feature libraries (`chart.js@4`, `livekit-client@2`).  
4. **Manifest** on server should list packages + allowed methods for `bridge.call`.  
5. Never commit `node_modules` into the Python wheel.

## DX checklist

- [ ] `ch.runtime()` includes `ux-bridge.js` when using widgets  
- [ ] Host element has `data-channel-bridge-id` + `data-channel-bridge-package`  
- [ ] Adapter registered before `bridge.mount` op arrives  
- [ ] Manifest methods match adapter `call` surface  
- [ ] Media uses `ch.media`, not bridge ops  

## Related

- [BRIDGE_STRATEGY.md](BRIDGE_STRATEGY.md) — planes split  
- [PLACEMENT.md](../start/PLACEMENT.md) — data not HTML  
- `ux_channel.bridge_api` — low-level helpers  
- `ux_channel.plugins.BridgeManifest` — contracts

## DX: `uxchannel bridge` (any npm package)

Because mapping is **string ops**, any npm UI package can be bridged:

```bash
uxchannel bridge explain
uxchannel bridge new chartjs --npm chart.js --methods update,resetZoom
uxchannel bridge recipe
```

Writes:

* `ux-bridge-<pkg>.js` — adapter (`mount/update/call/destroy`)
* `register.py` — `ch.bridge.register(...)` snippet
* `package.json` — peerDep on the real library

Then customize `mount()` for that library’s constructor. Python only ever sees package + method strings.

### Edit contract methods



Updates `contract.json` and syncs `register.py` methods=(...).
