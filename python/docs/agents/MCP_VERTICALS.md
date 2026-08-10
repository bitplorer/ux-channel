# MCP verticals, effects, sessions, resources

Agents use the **same** `@ch.on` actions as UI, marked with `@agent_tool`,
filtered by `AgentPolicy`, optional **vertical packs**, and optional
**claim-bound MCP sessions**.

## Surfaces

| Route | Role |
|-------|------|
| `GET /ux-channel/mcp/tools` | Tool list (policy ∩ verticals ∩ claim) |
| `POST /ux-channel/mcp/tools/call` | Tool call → Result + **effects** envelope |
| `POST /ux-channel/mcp/rpc` | JSON-RPC (`tools/*`, `resources/*`, `initialize`) |
| `GET /ux-channel/mcp/resources` | Resource list |
| `GET /ux-channel/mcp/resources/read?uri=` | Read situation / region / claim / verticals |
| `POST /ux-channel/mcp/session` | Mint claim-bound session (requires agent_token) |
| `POST /ux-channel/mcp/session/revoke` | Revoke session ticket |

Auth:

* **Bootstrap:** `Authorization: Bearer <agent_token>`
* **Session:** `Authorization: Bearer <session_ticket>` (from `/mcp/session`)

## Effects envelope

Every tool result includes `_meta.effects`:

```json
{
  "ok": true,
  "regions": ["cart"],
  "toasts": [{"level": "info", "message": "…"}],
  "ops": [{"op": "morph", "target": "…", "uid": "cart"}],
  "needs_confirmation": false,
  "dry_run": false
}
```

`confirmation_required` sets `needs_confirmation` + optional `confirm_token`
without treating the call as transport `isError`.

## Vertical packs

```python
from ux_channel.mcp import register_vertical, VerticalPack, register_builtin_verticals

register_builtin_verticals()  # pos + lab samples

ChannelConfig.development(
    …,
    mount_agent_mcp=True,
    agent_token="…",
    mcp_verticals=("pos",),
    mcp_resource_regions=("cart",),
)
```

Pack = tools + tags + default room/scopes + confirm/outbox/io hints.
Final allow = **marked ∩ policy ∩ pack ∩ claim scopes**.

## Confirmation ladder

1. Call high-stakes tool without `confirmation`  
2. Receive `confirm_token` in effects  
3. Re-call with same args + `confirmation: <token>`  
4. Token is args-bound, session-bound, one-time  

Shared secret string still accepted for tests/dev.

## Sessions

```bash
# mint
curl -s -H "Authorization: Bearer $TOKEN" -d '{"room":"pos","scopes":["pos"],"verticals":["pos"]}' \
  http://127.0.0.1:8080/ux-channel/mcp/session

# tools with session ticket
curl -s -H "Authorization: Bearer $TICKET" http://127.0.0.1:8080/ux-channel/mcp/tools
```

## Resources (read-only — not Quantity)

| URI | Body |
|-----|------|
| `uid://verticals` | Pack list |
| `uid://claim` | Room / scopes / sub |
| `uid://situation/{room}` | Situation snapshot |
| `uid://region/{uid}` | Region HTML (allowlisted) |
| `uid://outbox/{room}` | Outbox summary |

**Quantity** remains effect authority via `Quantity.from_store` in handlers.
Resources are observation only.

## Demo

```bash
UX_CHANNEL_AGENT_TOKEN=dev-token \
PYTHONPATH=src uvicorn examples.mcp_verticals.app:app --host 0.0.0.0 --port 8080
```

| Vertical | Tools | Room |
|----------|-------|------|
| **POS** | `pos_add_line`, `pos_pay`, `pos_queue_add`, `pos_drain` | `pos` |
| **Lab** | `lab_read`, `lab_flash` | `lab` |

## Related

[AGENTS.md](AGENTS.md) · [WORKPLACE.md](../workplace/WORKPLACE.md) · [IO_CHANNEL.md](../workplace/IO_CHANNEL.md) · [OUTBOX.md](../workplace/OUTBOX.md)

## P6 — Outbox / I/O annotations

Tool list entries include `annotations.ux_channel`:

```json
{
  "vertical": "pos",
  "kind": "outbox.queue",
  "confirm": false,
  "outbox": true,
  "scopes": ["pos", "pay", "…"],
  "requires_quantity": false
}
```

Kinds: `read` · `command` · `outbox.queue` · `io.read` · `io.command`.
`io.command` sets `requires_quantity: true` (hint; handler + IoGate still enforce).

## P7 — Redis MCP sessions

When `ChannelConfig.redis_url` is set, MCP sessions use `RedisMcpSessionStore`
(multi-worker mint/get/revoke). Otherwise memory store.

```python
ChannelConfig.development(...).with_redis("redis://…")
# or redis_url= on config
```

## P8 — Resource subscribe (SSE)

```text
JSON-RPC  resources/subscribe  → { topics, sse[], push[] }
GET /ux-channel/mcp/resources/subscribe?topic=mcp.resource.{room}
```

After each tool call, effects with regions publish:

```json
{ "event": "resource.updated", "uris": ["uid://region/cart", …], "reason": "tool_effects" }
```

Topic allowlist for sessions: room topic + session topic only.
