# Pulse Desk — uxchannel demo

**Day-1 only:** `Channel.boot` → `@region` → `@on` → `control` → `scripts` → `ch.webrtc`.

Shows two planes in one app:

| Route | What |
|-------|------|
| `/` | Server-driven desk — region morph, signed actions, draft state |
| `/call` | WebRTC mesh — data chat + optional camera/mic |

## Run

```bash
cd uxchannel pip install -e ".[fastapi]"
uvicorn examples.pulse_desk.app:app --host 0.0.0.0 --port 8080
```

Open **two browser tabs** on `/call` for P2P. Use http://localhost (secure context for camera).

## What to try

1. **Desk** — click *Pulse* / *Reset*; watch the badge morph without full page reload  
2. **Call** — open two tabs, join room, send chat, *Start camera*  
3. View source: no React — Python regions + channel ops + `UxWebRTC`

## Mental model

```text
print(Channel.mental_model())
# Day-1: boot → @region → @on → control → scripts → draft/done → webrtc
```

## Bugs fixed (demo)

| Bug | Fix |
|-----|-----|
| Note field never sent | Use `ch.form(pulse)` + `type="submit"` so `Intent.form` merges freeform fields |
| Cap sealed empty vs freeform | Empty-args cap; form fields not required in cap (`verify_form_in_cap=False`) |
| Nested `data-channel-id` | Morph targets wrapper `pulse.badge` only — no inner id clash |
| Call page `UxWebRTC is undefined` | Wait for deferred `ux-webrtc.js` (`bootWhenReady`) |
| `ch.form(callable)` TypeError | Library: `Channel.form` resolves callables like `control` |

