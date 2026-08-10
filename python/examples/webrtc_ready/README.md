# WebRTC Ready

**Channel = plugin/signaling. App = UI.**

```bash
PYTHONPATH=src uvicorn examples.webrtc_ready.app:app --host 0.0.0.0 --port 8080
```

```python
p = ch.webrtc.plugin("lobby", sub=user_id)
# place script_tags(p) + attr_string(p); join with p.client
# your video/buttons/CSS stay in the app
```

| Route | What |
|-------|------|
| `/` | example-local UI + plugin |
| `/plugin.json` | placement bag only |
| `/health` | diagnose |
