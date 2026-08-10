# Examples — uxchannel 0.1

All demos assume:

```bash
cd <repo-root>
pip install -e ".[fastapi,dev]"
export PYTHONPATH=src
# ux-dom demos also need ux_dom on PYTHONPATH
```

| App | Port tip | Shows |
|-----|----------|--------|
| [channel_demo](./channel_demo/) | 8080 | Minimal channel DX |
| [counter](./counter/) | 8080 | Actions, caps, async |
| [forms](./forms/) | 8081 | Validation, focus, navigate |
| [plugins_demo](./plugins_demo/) | 8082 | Renderer + bridge |
| [composites_demo](./composites_demo/) | 8080 | AppShell / Cart / DataTable |
| [components_demo](./components_demo/) | 8080 | Channel components |
| [agent_mcp](./agent_mcp/) | 8090 | MCP tools + agent token |
| [live_actions](./live_actions/) | 8080 | After-hook action console |
| [ux_dom_shop](./ux_dom_shop/) | 8080 | ux-dom + class regions |
| [ux_dom_dashboard](./ux_dom_dashboard/) | 8080 | Dashboard charts (SVG) |
| [ux_dom_chartjs](./ux_dom_chartjs/) | 8080 | Chart.js npm bridge |
| [ux_dom_threejs](./ux_dom_threejs/) | 8080 | three.js 3D bridge |
| [sarrafa_market](./sarrafa_market/) | 8080 | Gold/silver market tracker |
| [sse_live_ticker](./sse_live_ticker/) | 8080 | SSE auto-tick (no clicks) |
| [ws_live_board](./ws_live_board/) | 8080 | WebSocket duplex + ux-dom |

```bash
uvicorn examples.ws_live_board.app:app --host 0.0.0.0 --port 8080
```

Docs: [../docs/start/HOW_TO.md](../docs/start/HOW_TO.md) · [../docs/dx/EXAMPLES.md](../docs/dx/EXAMPLES.md)

- **pulse_desk** — day-1 demo: live desk (regions) + WebRTC call room

- **io_mesh_workplace** — I/O channel demo (scan≡button≡agent, party room, lab flash)
- **workplace_pos** — hardened POS (tickets, require_cap, Quantity, wp.control)
- **workplace_lab** — lab cell (flash budget, membership, logout revoke)
- **workplace_kit** — starter kit (membership, outbox, MCP)
- **mcp_verticals** — POS + Lab MCP tools on Workplace
