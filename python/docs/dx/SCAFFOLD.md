<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Scaffolding — plug-and-play DX

Create a runnable uxchannel app with **defaults that work on day 1**.

## Commands

```bash
# Recommended — full project tree
uxchannel create-app myapp
uxchannel create-app myapp --template webrtc
uxchannel create-app shop --template full --uxdom uxchannel create-app demo -t live --port 8080

# List templates
uxchannel create-app --list-templates

# Validate a tree (CI)
ux_channel scaffold-check ./myapp

# Legacy single file
uxchannel new --path app.py
```

## Templates

| Template | Defaults | Intent |
|----------|----------|--------|
| **minimal** | memory stores, counter region | Smallest morph demo |
| **live** | multi-region board | Several morph targets |
| **webrtc** | scripts + A/V UI | Data channel + camera/mic |
| **full** | live + `/call` WebRTC | Structured multi-page |

All templates:

* `ChannelConfig.development` via `app/config.py`
* `.env` with generated secret (gitignored)
* `requirements.txt` + `README.md` + `docs/foundations/ARCHITECTURE.md`
* `uvicorn app.main:app` entry

## Defaults (why)

| Default | Why |
|---------|-----|
| `allow_memory_stores=True` | No Redis to say hello |
| `webrtc_enabled=True` | Signaling + JS out of the box |
| `require_channel_header=False` (dev) | Less friction in demos |
| Port `8080` | Common preview port |
| Secret in `.env` | Not baked into source for git |

Production: set `UX_CHANNEL_ENV=production`, strong secret, Redis, TURN.

## Layout

```text
myapp/
  README.md
  requirements.txt
  .env / .env.example
  .gitignore
  app/
    __init__.py
    config.py      # get_channel_config()
    main.py        # boot + routes (commented)
  scripts/run.sh
  docs/foundations/ARCHITECTURE.md
```

## Library API

```python
from ux_channel.scaffold import create_app, ScaffoldOptions, validate_scaffold

root = create_app(ScaffoldOptions(app_name="demo", template="webrtc"))
assert validate_scaffold(root)["ok"]
```

## Maintaining templates

Edit only `ux_channel/scaffold/create.py`:

1. Add name to `_TEMPLATES`
2. Add `_main_*` generator
3. Document in this file + tests
4. Keep **comments in generated code** — they are the DX surface

Do not generate code that requires Redis, TURN, or ux-dom unless the user opted in.
