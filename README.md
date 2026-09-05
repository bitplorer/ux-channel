# ux-channel

[![CI](https://github.com/bitplorer/ux-channel/actions/workflows/ci.yml/badge.svg)](https://github.com/bitplorer/ux-channel/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A click is not a form post. It is a signed **Intent**.

```text
Intent {action, args, cap}  →  verify  →  action  →  Result {ok, ops[]}
```

JSON is the floor. Caps authorize. Classic IR 0.1 stays valid. Channel is the product. **cek-runtime Host** is the default Cap machine (`cek=require`; wrap via `[cek]` — [ADR 0008](SPEC/architecture/ADR/0008-cek-runtime-kernel-ssot.md) / [0010](SPEC/architecture/ADR/0010-channel-cek-runtime-default-cut3.md)). `cek=off` is the explicit escape.

This layer **owns the wire**: Intent, Result, Capability, codecs, peers, host runtime. It does **not** own HTML trees or CSS.

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |
| **Version** | `0.1.0` |
| **Python** | ≥ 3.10 |
| **License** | [MIT](LICENSE) |

## Table of Contents

- [Install](#install)
- [Usage](#usage)
- [Ownership](#ownership)
- [Audience](#audience)
- [Documentation](#documentation)
- [API](#api)
- [Verify](#verify)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

## Install

```bash
pip install "ux-channel[asgi]"
pip install "ux-channel[cek]"    # default Cap machine: cek-host + cek-surface ≥ 0.1.3
```

Extras: `asgi` / `fastapi` / `starlette`, `redis`, `speed`/`serde` (`orjson`), `cek`, `otel`/`devtools`, `full`.

## Usage

The product is Intent → Result. HTTP is optional.

```python
from ux_channel import Channel, ChannelConfig, Intent

ch = Channel.boot(config=ChannelConfig.development(secret="dev-" + "x" * 32))

@ch.on
def ping():
    return ch.done()

ch.registry.dispatch(Intent(action="ping", args={}, cap=ch.mint("ping", {})))
```

FastAPI is an L3 adapter (`asgi/`), not the core:

```python
from fastapi import FastAPI
from ux_channel import Channel, ChannelConfig

app = FastAPI()
ch = Channel.boot(app, config=ChannelConfig.development(secret="dev-" + "x" * 32))

@ch.on
def ping():
    return ch.done()
```

Package map: [python/src/ux_channel/LAYERS.md](python/src/ux_channel/LAYERS.md). L4 planes (`ch.webrtc`, `ch.media`, `ch.bridge`) attach on first use.

`async def` handlers use `await ch.registry.async_dispatch(...)`. `dispatch()` refuses them — it does not start an event loop.

```bash
uxchannel create-app myapp
cd myapp && pip install -r requirements.txt
uvicorn app.main:app --reload   # click +1 — that is the first morph
```

Do **not** ship `development(secret=…)` in production. Five-minute path: [START_HERE.md](START_HERE.md) is the only intro.

## Ownership

| Owns | Does **not** own |
|------|------------------|
| Intent / Result / Cap / args_hash | HTML trees, CSS, Document (`ux-dom`) |
| Wire codecs (JSON floor, CXB upgrade) | MorphState / `@action` (`ux-behavior`) |
| Host runtime, peers, regions protocol | Motion IR (`ux-motion`) |
| `uxchannel` CLI + conformance vectors | Product serve (`ux-compose`) |

## Audience

| You are… | Start |
|----------|--------|
| **New** | [START_HERE.md](START_HERE.md) |
| **Python host builder** | [python/docs/start/GOLDEN_PATH.md](python/docs/start/GOLDEN_PATH.md) |
| **Need frozen names** | [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) |
| **Operator** | [OPERATIONAL.md](OPERATIONAL.md) |
| **Map** | [docs/INDEX.md](docs/INDEX.md) |
| **Security** | [SECURITY.md](SECURITY.md) |
| **Questions** | [SUPPORT.md](SUPPORT.md) |

## Documentation

Family contract: [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md). Map: [docs/INDEX.md](docs/INDEX.md).

| Diátaxis | Canonical |
|----------|-----------|
| Tutorial | [START_HERE.md](START_HERE.md) |
| How-to | [docs/guides/first-app.md](docs/guides/first-app.md) |
| Reference | [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) |
| Explanation | [MENTAL_MODEL.md](MENTAL_MODEL.md) · [HOW_IT_WORKS.md](HOW_IT_WORKS.md) |

## API

Root `ux_channel.__all__`: `Channel`, `ChannelConfig`, `create_channel`, `Intent`, `Result`, `Op`, `CapService`, `morph`, `toast`, `navigate`, `ActionRegistry`, `Region`, `action_attrs`, `esc`, and the rest of the freeze. CLI: `uxchannel`. Frozen names: [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md).

## Verify

```bash
export UX_CHANNEL_STRICT_DX=1
uxchannel doctor --fail
make verify
```

## Security

Caps, `args_hash`, JTI/once, fail-closed unknown actions. Morph HTML escaping is the caller’s. [SECURITY.md](SECURITY.md).

## Contributing

PRs welcome. [CONTRIBUTING.md](CONTRIBUTING.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) · [SUPPORT.md](SUPPORT.md) · [GOVERNANCE.md](GOVERNANCE.md).

## License

MIT — see [LICENSE](LICENSE).
