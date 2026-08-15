# ux-channel

A click is not a form post. It is a signed **Intent**.

```text
Intent {action, args, cap}  →  verify  →  action  →  Result {ok, ops[]}
```

JSON is the floor. Caps authorize. Classic IR 0.1 clients stay valid forever.

## Install

```bash
pip install "ux-channel[asgi]"
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

## First 5 minutes

```bash
uxchannel create-app myapp
cd myapp && pip install -r requirements.txt
uvicorn app.main:app --reload   # click +1 — that is the first morph
```

**New here? [START_HERE.md](START_HERE.md) is the only intro.**

| Next | When |
|------|------|
| [MENTAL_MODEL.md](MENTAL_MODEL.md) | one-page model |
| [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) | frozen names |
| [GOLDEN_PATH](python/docs/start/GOLDEN_PATH.md) | copy-paste cart |
| [SECURITY_AUDIT](python/docs/security/SECURITY_AUDIT.md) | ship checklist |
| [TESTING.md](TESTING.md) | what green means |
| [DOCS.md](DOCS.md) | pyramid index |

```bash
export UX_CHANNEL_STRICT_DX=1
uxchannel upgrade-check . --fail
uxchannel doctor --fail
make verify
```
