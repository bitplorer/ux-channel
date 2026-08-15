<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Agents + MCP (full surface)

AX application remains **`agents(ch)`**. MCP is an optional **HTTP/JSON-RPC viewport**
onto the same registry — never a second product.

## Application (always)

```python
from ux_channel import agents

ag = agents(ch)
ag.tools_for()
ag.situation(facts={...})
ag.dispatch("pay_order", {"order_id": "…"}, peer=ag.peer("bot-1"))
ag.effects(result)
```

## MCP mount (power)

```python
ChannelConfig.development(
    mount_agent_mcp=True,
    agent_token="…",                 # bootstrap only
    agent_confirmation_secret=…,     # optional; falls back to secret
    mcp_verticals=("pos", "lab"),
    mcp_resource_regions=("cart",),
    mcp_session_ttl_s=900,
    # redis_url=…  → RedisMcpSessionStore
)
app.state.uid_agent_policy = AgentPolicy.production(allow=[…], confirm=[…])
```

### Routes

| Method | Path | Auth |
|--------|------|------|
| GET | `/ux-channel/mcp/tools` | agent_token or session ticket |
| POST | `/ux-channel/mcp/tools/call` | same |
| POST | `/ux-channel/mcp/rpc` | JSON-RPC tools/resources/initialize |
| GET | `/ux-channel/mcp/resources` | list |
| GET | `/ux-channel/mcp/resources/read?uri=` | read |
| GET | `/ux-channel/mcp/resources/subscribe?topic=` | SSE invalidation |
| POST | `/ux-channel/mcp/session` | **agent_token only** (mint) |
| POST | `/ux-channel/mcp/session/revoke` | token or session |

### Effects (`_meta.effects`)

Normalized from `Result`: `ok`, `ops`, `regions`, `toasts`, `needs_confirmation`,
`confirm_token`, `dry_run`, …  See [MCP_VERTICALS.md](MCP_VERTICALS.md).

### Modules (import map)

| Module | Role |
|--------|------|
| `ux_channel.mcp.adapter` | McpToolAdapter list/call/rpc |
| `ux_channel.mcp.effects` | `effects_from_result` |
| `ux_channel.mcp.verticals` | VerticalPack registry |
| `ux_channel.mcp.annotations` | tools/list enrichment |
| `ux_channel.mcp.confirm` | signed confirm tokens |
| `ux_channel.mcp.sessions` | memory / Redis sessions |
| `ux_channel.mcp.resources` | uid:// readers |
| `ux_channel.mcp.subscribe` | SSE topics + publish |
| `ux_channel.mcp.asgi_routes` | adapter factory + auth resolve |

### Security notes

* Browser **X-Channel** is for browser Intents; MCP uses bearer tickets.
* Resource ≠ Quantity (read context vs effect authority).
* Final tool allow = marked ∩ policy ∩ pack ∩ claim.
* Confirm tokens bind action + args_hash + session + agent; one-time jti.
* Tool list carries ``annotations.ux_channel`` (vertical, kind, outbox, confirm).

Related: [AGENTS.md](AGENTS.md) · [MCP_VERTICALS.md](MCP_VERTICALS.md) · [WORKPLACE.md](../workplace/WORKPLACE.md)
