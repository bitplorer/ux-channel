# Live Actions Console (demo)

**Not part of the uxchannel library** — a standalone demo app.

Shows a live view of a Channel:

- Action catalog (`action_catalog`)
- Regions + `diagnose()`
- Dispatch histogram
- Live feed via `@ch.after` (demo-local telemetry)

## Run

```bash
cd ux-channel-repo
PYTHONPATH=src:/path/to/ux_dom:. \
  uvicorn examples.live_actions.app:app --host 0.0.0.0 --port 8080
```

Click **Ping / Add item / Demo fail / Slow** to populate the feed.
