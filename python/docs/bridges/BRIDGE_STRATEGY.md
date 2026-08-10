# Bridge & npm strategy (long-term stability)

## Two different jobs (do not merge)

| Job | Python surface | Client | Lifecycle |
|-----|----------------|--------|-----------|
| **Widget bridge (island)** | `ch.bridge` / `bridge_api` | adapter registered in `ux-bridge.js` | mount → update → call → destroy |
| **Media plane** | `ch.media` | **battle-tested npm** (`livekit-client`) or mesh runtime | join / leave / tracks — **not** bridge ops |
| **Channel protocol** | `ch.control`, regions | `ux-channel.js` | Intent → Result → morph |

**Rule:** LiveKit is **not** a Chart.js-style bridge. Putting multiparty media into `bridge.mount` couples room tokens to widget DOM ids and ages poorly.

```text
ux-dom / templates
       │
  ch.control / regions     ← app control
  ch.bridge.*              ← optional npm WIDGETS (charts, maps, editors)
  ch.media.*               ← realtime media (mesh | SFU client)
       │
  packages/@ux-channel/*  ← npm workspace (source of adapters)
  src/ux_channel/static/*  ← only *protocol* JS shipped with PyPI
```

## Where JS lives

### Ship with the Python wheel (keep small)

```text
src/ux_channel/static/
  ux-channel.js      # protocol runtime (required)
  ux-bridge.js       # generic bridge host loader (required for widgets)
  ux-webrtc.js       # mesh ferry client (optional plane)
  ux-sfu-livekit.js  # TINY boot only — does NOT vendor livekit-client
  ux-inspector.js    # dev
```

These are **protocol glue**, versioned with `uxchannel` Python releases.

### npm monorepo (app upgrades independently)

```text
packages/
  @ux-channel/bridge-core     # types + register() helpers for adapters
  @ux-channel/adapter-*       # chartjs, three, maps… (optional publish)
  @ux-channel/media-livekit   # thin peerDep on livekit-client (optional)
```

Apps do:

```bash
npm i livekit-client @ux-channel/media-livekit   # app owns versions
# or CDN for demos only
```

**Why not vendor livekit-client in PyPI static/?**  
You lag “features millions use”, bloat the wheel, and fight dual versioning. Channel mints **tokens**; npm owns **media SDK**.

## Recommended folder names

| Path | Use |
|------|-----|
| `packages/` | Preferred monorepo root (npm workspaces / pnpm) |
| `packages/@ux-channel/*` | Scoped packages |
| `npm/` | Alias symlink to `packages/` if you like the name |
| `bridge/npm/` | **Avoid** — implies all bridges equal media |

Do **not** put app `node_modules` into the Python package.

## Python API shape (stable)

```python
# Widgets (islands) — existing ops, clearer home
ch.bridge.host(id, package="chartjs", props={...})   # HTML shell
ch.bridge.mount_ops(...)                             # Result ops
ch.bridge.manifests                                  # optional validation

# Media — never under bridge.mount lifecycle
ch.media.plugin(room, sub=user)                      # mesh | sfu bag

# Explicit non-alias (teaching)
# ch.bridge.media  →  NOT a widget; redirects mentally to ch.media
```

If you expose `ch.bridge.media` for discoverability, it must be a **thin alias** to `ch.media` with docs saying “not an island”, **not** a `bridge.mount` package.

## Versioning contract

| Artifact | Version with |
|----------|----------------|
| `ux-channel.js` wire | Python `uxchannel` major |
| `ux-bridge.js` op names | Python major (additive ops OK) |
| `@ux-channel/*` npm | Own semver; peerDep on host libs |
| `livekit-client` | **App** package.json only |

## Security / distribution

1. Plugin bags never embed long-lived SFU secrets (token only).  
2. Widget bridges: allowlisted methods via `BridgeManifest`.  
3. `upgrade-check` can flag hand-rolled CDN of random SFU SDKs later.  
4. PyPI static/ is allowlisted paths only (existing static mount).

## Migration

| Today | Long-term |
|-------|-----------|
| `from ux_channel.bridge.bridge_api import …` | `ch.bridge.*` day-1 optional layer |
| `ch.media.plugin` | unchanged canonical media API |
| CDN livekit in plugin scripts | app `npm i` or optional `@ux-channel/media-livekit` |
| Ad-hoc `static/*.js` adapters | `packages/@ux-channel/adapter-*` |

## What not to do

* Fold LiveKit into `bridge.mount` / `bridge.call`  
* Ship full `livekit-client` inside the wheel  
* One mega `@ux-channel/all` package  
* Framework-specific React/Vue wrappers inside **this** repo’s day-1 (publish separately if needed)  
* `ch.bridge.media` that returns a different lifecycle than `ch.media`

---

*Summary: protocol JS in Python static/; real npm SDKs in `packages/` with peerDeps; `ch.bridge` = widgets; `ch.media` = media. Stability comes from that split.*
