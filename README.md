# ux-channel

A click is not a form post. It is a signed **Intent**.

```text
Intent {action, args, cap}  →  verify  →  action  →  Result {ok, ops[]}
```

JSON is the floor. Caps authorize. Classic IR 0.1 stays valid.
Channel is the product. **cek-host 0.1.3** is the optional Cap machine (`cek=require`).

This layer **owns the wire**: Intent, Result, Capability, codecs, peers, host runtime.
It does **not** own HTML trees or CSS. Markup is the caller's (ux-dom, Jinja, or other).

> **New here?** [START_HERE.md](START_HERE.md) is the only intro.
> **Map:** [docs/INDEX.md](docs/INDEX.md) · encyclopedia: [DOCS.md](DOCS.md)
> **Contributor / agent:** [CONTRIBUTING.md](CONTRIBUTING.md) · [AGENTS.md](AGENTS.md)

## Install

```bash
pip install "ux-channel[asgi]"
pip install "ux-channel[cek]"    # optional: cek-host + cek-surface ≥ 0.1.3
```

## Eight lines

```python
from fastapi import FastAPI
from ux_channel import Channel, ChannelConfig

app = FastAPI()
ch = Channel.boot(app, config=ChannelConfig.development(secret="dev-" + "x" * 32))

@ch.on
def ping():
    return ch.done()
```

`async def` handlers use `await ch.registry.async_dispatch(...)`.
`dispatch()` refuses them — it does not start an event loop.

## First 5 minutes

```bash
uxchannel create-app myapp
cd myapp && pip install -r requirements.txt
uvicorn app.main:app --reload   # click +1 — that is the first morph
```

### Ownership

| Owns | Does **not** own |
|------|------------------|
| Intent / Result / Cap / args_hash | HTML trees, CSS, Document shell (`ux-dom`) |
| Wire codecs (JSON floor, CXB upgrade) | Product MorphState / `@action` (`ux-behavior`) |
| Host runtime, peers, regions protocol | Motion IR (`ux-motion`) |
| `uxchannel` CLI + conformance vectors | Author composition / product serve (`ux-compose`) |

### Audience

| You are… | Start |
|----------|--------|
| **New** | [START_HERE.md](START_HERE.md) |
| **Python host builder** | [python/docs/start/GOLDEN_PATH.md](python/docs/start/GOLDEN_PATH.md) |
| **Need frozen names** | [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) |
| **Operator** | [OPERATIONAL.md](OPERATIONAL.md) · [TESTING.md](TESTING.md) |
| **Contributor / agent** | [CONTRIBUTING.md](CONTRIBUTING.md) · [AGENTS.md](AGENTS.md) |
| **Need a map** | [docs/INDEX.md](docs/INDEX.md) |

```bash
export UX_CHANNEL_STRICT_DX=1
uxchannel upgrade-check . --fail
uxchannel doctor --fail
make verify
```
