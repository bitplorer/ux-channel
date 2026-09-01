# @uxchannel npm workspace

**Bridging npm packages via uxchannel is fully supported.**

Protocol runtime (`ux-bridge.js`) ships with the **Python** package.  
Widget **adapters** and heavy libs ship via **npm** (this workspace or the app).

See [docs/bridges/NPM.md](../docs/bridges/NPM.md).

## Packages

| Package | Plane | Notes |
|---------|-------|-------|
| `@ux-channel/bridge-core` | **widget bridge** | `defineAdapter` → `uxBridge.register` |
| `@ux-channel/media-livekit` | **media** (not bridge ops) | peerDep `livekit-client` |

## App flow (widget)

1. `npm i chart.js @ux-channel/bridge-core`
2. Register adapter in your bundle
3. Python: `ch.bridge.register("chart.js", methods=("update",))`
4. Place host: `ch.bridge.mount_spec(...)` → your HTML
5. Ops: `ch.bridge.mount_ops(...)`

## Media flow (not bridge.mount)

1. `npm i livekit-client`
2. Python: `ch.media.plugin(room, sub=user, mode="sfu")`
3. Connect with SDK / `@ux-channel/media-livekit`
