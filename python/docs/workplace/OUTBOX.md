# Intent outbox

**Power module:** `from ux_channel.outbox import MemoryIntentOutbox, drain_outbox, attach_outbox`

## Law

Queued work is still **Intent-shaped**. Drain uses the same
`Workplace.dispatch` / registry path — no second mutation door.

```text
offline / partition → enqueue(action, args)
online              → drain_outbox → dispatch → Result
```

## API

```python
from ux_channel.outbox import attach_outbox, drain_outbox, MemoryIntentOutbox

box = attach_outbox(ch, MemoryIntentOutbox())
# or RedisIntentOutbox(redis_url) multi-worker

item = box.enqueue(
    "add_line", {"sku": "SKU-100"},
    room=wp.claim.room, peer_id=wp.claim.peer_id,
    scopes=tuple(wp.claim.scopes),
    idempotency_key="…",
)

def dispatch(action, args, item):
    return wp.dispatch(action, dict(args))

stats = drain_outbox(box, dispatch, batch=20)
```

## Statuses

`pending` → `draining` → `done` | `failed` → (retry) | `dead` (max attempts)

## Kit demo

`examples/workplace_kit` — **Queue add** then **Drain outbox**.

## MCP

Outbox tools are annotated via vertical packs (`annotations.ux_channel.outbox`). See [MCP_VERTICALS.md](../agents/MCP_VERTICALS.md).
