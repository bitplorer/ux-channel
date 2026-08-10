# ux-dom + uxchannel + three.js (3D)

Yes — **any interesting npm package** can be driven the same way as Chart.js:

1. Write a small **ux-bridge adapter** (`uxBridge.register("three", { mount, update, call })`)
2. SSR a host with `mount_html(..., package="three", props=...)`
3. Channel actions return `bridge.update` / `bridge.call` ops
4. ux-dom + **regions** handle the non-WebGL chrome

This demo loads **three.js@0.160** from jsDelivr (npm package on CDN), mounts a WebGL scene, and controls it from Python actions.

## Run

```bash
PYTHONPATH=src:/tmp/ux_dom \
  uvicorn examples.ux_dom_threejs.app:app --host 0.0.0.0 --port 8080
```

## Try

- **Next shape** — torus / box / icosahedron / sphere  
- **Next color** · **Wireframe** · **Toggle spin** · **Faster/Slower** · **Pulse**  
- **Drag** the canvas to orbit  

## Pattern for other 3D packages

| Package | Adapter idea |
|---------|----------------|
| `three` | This demo |
| `@babylonjs/core` | Same mount/update/call; heavier CDN |
| `globe.gl` | Props → points/arcs; bridge.update on data |
| `3d-force-graph` | Graph data in props; call `refresh` |

You never vendor the whole npm tree into Python — only a thin adapter + ops.
