# Pulse × ux-dom

How to implement **Pulse Desk** capabilities **with ux-dom** without mixing jobs.

| Layer | Owns |
|-------|------|
| **ux-dom** | `Document`, `Component`, tags, layout, SSR HTML |
| **ux-channel** | `Channel.boot`, regions, actions, `control`, caps, `scripts()`, `body_attr_string()`, `ch.webrtc` |

```bash
PYTHONPATH=src:. uvicorn examples.pulse_ux_dom.app:app --host 0.0.0.0 --port 8080
```

See module docstring in `app.py` for the full pattern.
