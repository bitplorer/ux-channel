**First-time users:** [START_HERE.md](../../../START_HERE.md) (mental model, caps, mistakes, checklist).

# Course correction — long-term architecture (0.1)

**Library version:** 0.1.0 (brand **0.1**).

## Domain (what this library is for decades)

**Server-driven UI protocol runtime for Python web apps:**

```text
Browser --Intent+cap--> Host --> Registry --> Action
                              <-- Result(ops) --
```

- **Not** a React replacement, design system, or full-stack framework.
- **Is** the Intent/Action/Result spine, signed capabilities, region morphs,
  live push, and plug-in bridges to any JS package.

## Layers (import where they live)

| Layer | Package path | Owns |
|-------|----------------|------|
| **Core** | `uxchannel` | Intent, Result, ops, Channel, Region, caps, draft, control |
| **Host** | `ux_channel.asgi` | FastAPI / Starlette routes, CSRF header, static JS |
| **Live** | `ux_channel.live`, `.push` | topic→region map, SSE/WS bus |
| **Security** | `ux_channel.*_security`, `.policy` | tickets, origin, rate, events |
| **Bridge** | `ux_channel.bridge_api` | npm host elements + mount/update ops |
| **Components** | `ux_channel.components` | *optional* channel-side blocks (not ux-dom) |
| **Agents** | `ux_channel.agent_runtime`, `.mcp` | optional agent/tool plane |
| **Redis** | `ux_channel.redis_extra` | multi-worker stores |
| **Demo** | `ux_channel.render.kit` | raw HTML page/button (examples only) |

## Rules that stay true for decades

1. **HTML libraries own trees** — Channel wires `control` / `trust_*`, does not compete as a widget kit.
2. **One name per concept** — region, refresh, notice, control, trust, draft, bridge (not island).
3. **Fail closed** — caps, CSRF (prod), unsafe navigate, push tickets.
4. **Retries only when safe** — `idempotent=True` on actions for automatic batch retry; once-caps never magically re-run.
5. **Live.bind is in-process** — Redis is the multi-worker transport; do not conflate them.
6. **Extras never pollute core imports** — agents/MCP/components stay optional.

## Product vocabulary (closed)

Channel · Region · Action · Control · Trust · Draft · Op · Bridge · Live · Push

## Anti-goals (do not grow into)

- Second React / SPA runtime
- Mandatory component library
- ORM or business domain layer
- Replacing ux-dom for markup

## Migration notes (pre-public)

- `mount_html` → `mount_html` (bridge_api)
- `ch.fail.valid` → `ch.fail.valid`
- `ch.fail.rate` → `ch.fail.rate`
- `Result.failure` remains (wire synonym of `Result.fail`)
- Top-level `from ux_channel import BridgeManifest, …` → submodule imports
