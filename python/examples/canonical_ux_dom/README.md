# Canonical uxchannel board

Preferred 0.1 shape:

- `Region` + `@Region.action` (not low-level `@ch.action`)
- `ch.control(...)` for buttons
- `ch.live.bind` + `publish` / `broadcast=`
- Production: `ChannelConfig.production(secret).with_redis(REDIS_URL)`

```bash
uvicorn examples.canonical_ux_dom.app:app --host 0.0.0.0 --port 8080
```

Multi-worker:

```bash
export UX_CHANNEL_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
export REDIS_URL=redis://127.0.0.1:6379/0
uvicorn examples.canonical_ux_dom.app:app --host 0.0.0.0 --port 8080 --workers 2
```
