# WebSocket live board (ux-dom + uxchannel 0.1)

Demo of **duplex WebSocket** usability:

| Feature | How |
|---------|-----|
| Auto-connect | `data-channel-ws` + `uidChannel.subscribeWs()` |
| Multi-topic live morphs | ticker / tape / status / private over **one** socket |
| Feeder | `PushBus.publish` → WS `type:result` → `applyResult` |
| Actions | Region buttons with caps (Intent; client may use POST or WS) |
| Private topic | `ch.sign_ws("shop.ws.pulse")` on the page |
| DX log | on-page hello / subscribed / result lines |

## Run

```bash
PYTHONPATH=src:/tmp/ux_dom uvicorn examples.ws_live_board.app:app --host 0.0.0.0 --port 8080
```

Open the preview — leave it open to see auto-ticks; try **Bump**, **Shout**, **Private +1**, **Ping socket**.

## Related

- [docs/asgi/WEBSOCKET.md](../../docs/asgi/WEBSOCKET.md)
- [examples/sse_live_ticker](../sse_live_ticker/) (SSE-only sibling)

## Security notes (demo)

- `push_require_auth=True` even in development so **`shop.ws.pulse` needs the page ticket**
- `public.*` topics stay open
- Shout/tape text is escaped once by ux-dom (not pre-escaped in handlers)
