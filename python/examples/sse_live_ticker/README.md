# SSE auto-tick (ux-channel)

Live board **without client clicks**.

```text
feeder (asyncio) → ch.refresh → PushBus.publish
        ↓
GET /ux-channel/push/live.board  (SSE)
        ↓
EventSource → uidChannel.applyResult → morph regions
```

## Run

```bash
PYTHONPATH=src:/tmp/ux_dom \
  uvicorn examples.sse_live_ticker.app:app --host 0.0.0.0 --port 8080
```

Open the page and watch gold/silver tick with **no interaction**.  
Optional: Pause / Resume / Manual tick / Faster / Slower.

## Production notes

- Set `ChannelConfig.push_token` so SSE is not public.
- Multi-worker: Redis push bus (`REDIS_URL` / factory).
- Keep morph targets small (ticker strip), not full pages.

## Client (0.1)

Auto-subscribe: `attr_string(ch.body_attrs(push_topic="live.board"))`.
No hand-rolled EventSource required.
