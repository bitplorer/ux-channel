# Start here — ux-channel

**Audience:** first-time users of this package.
**Promise:** a running morph in five minutes.
**Time:** ~5 minutes (`uxchannel create-app`). Encyclopedia sections moved to `docs/` (Phase 2).

**Map:** [docs/INDEX.md](docs/INDEX.md).

**In 5 minutes**

```bash
pip install "ux-channel[asgi]"
uxchannel create-app myapp
cd myapp && pip install -r requirements.txt
uvicorn app.main:app --reload
```

Click **+1**. That is Intent → Result → morph. Then come back here for why.

**Cookbook:** [docs/guides/SNIPPETS.md](docs/guides/SNIPPETS.md) — boot, Caps, Intent/Result, ops, fail-closed, usage patterns.

**The product is the protocol, not HTTP.** Headless first:

```python
from ux_channel import Channel, ChannelConfig, Intent

ch = Channel.boot(config=ChannelConfig.development(secret="dev-" + "x" * 32))

@ch.on
def ping():
    return ch.done()

cap = ch.mint("ping", {})
ch.registry.dispatch(Intent(action="ping", args={}, cap=cap))
```

FastAPI is an L3 adapter (Door F). HTTP when a browser must reach the host:

```python
from fastapi import FastAPI
from ux_channel import Channel, ChannelConfig, morph, toast

app = FastAPI()
ch = Channel.boot(app, config=ChannelConfig.development(secret="dev-" + "x" * 32))

@ch.on
def ping():
    return ch.done()

@ch.on
def add(sku: str = "tee"):
    return ch.done()  # handlers return Result; prefer ch.done() / ch.fail()

# Caps: minted into button attrs
attrs = ch.control(add, trust_sku="tee").as_dict()
```

Folder map (3 minutes): [python/src/ux_channel/LAYERS.md](python/src/ux_channel/LAYERS.md).

Wire types you will actually import:

```python
from ux_channel import Intent, Result, CapService, morph, toast

intent = Intent(action="cart.add", args={"sku": "tee"})
ok = Result.success(morph("#cart", "<div id='cart'>1</div>"), toast("Added"))
caps = CapService(secret="dev-" + "x" * 32)
token = caps.mint("cart.add", {"sku": "tee"})
```

**Async:** `@ch.on async def …` is legal. Call `await ch.registry.async_dispatch(intent)`.  
`dispatch()` refuses async handlers — it will not nest an event loop.

**CEK (default decide):** `Channel.boot` uses cek-runtime Host (`cek=require`). Install `pip install "ux-channel[cek]"` (or rely on the promoted wrap deps). Bare-install escape: `cek="off"` / `UX_CHANNEL_CEK=off`. Channel stays the product ([ADR 0008](SPEC/architecture/ADR/0008-cek-runtime-kernel-ssot.md) / [0009](SPEC/architecture/ADR/0009-channel-cek-runtime-host-cut2.md) / [0010](SPEC/architecture/ADR/0010-channel-cek-runtime-default-cut3.md)).

| You want… | Open |
|-----------|------|
| The one idea | [docs/internals/identity.md](docs/internals/identity.md) |
| Words that matter | [docs/reference/vocabulary.md](docs/reference/vocabulary.md) |
| End-to-end loop | [docs/guides/application-loop.md](docs/guides/application-loop.md) |
| Security (caps) | [docs/reference/capabilities.md](docs/reference/capabilities.md) |
| Regions & morph | [docs/guides/regions-and-morph.md](docs/guides/regions-and-morph.md) |
| State (session/client/db) | [docs/reference/state-planes.md](docs/reference/state-planes.md) |
| First working app (hand-written) | [docs/guides/first-app.md](docs/guides/first-app.md) |
| Design *why* | [docs/adr/001-design-choices.md](docs/adr/001-design-choices.md) |
| What lives where (code map) | [docs/internals/implementation-map.md](docs/internals/implementation-map.md) |
| Import rules | [docs/reference/import-rules.md](docs/reference/import-rules.md) |
| Mistakes we see | [docs/guides/common-mistakes.md](docs/guides/common-mistakes.md) |
| Deeper reading | § below |

Related maps: [docs/INDEX.md](docs/INDEX.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [DOCS.md](DOCS.md) · [MENTAL_MODEL.md](MENTAL_MODEL.md) · [LONGEVITY.md](LONGEVITY.md) · [TERMINOLOGY.md](TERMINOLOGY.md)

---

## Where to go next

| Path | Doc |
|------|-----|
| Mental model (short) | [MENTAL_MODEL.md](MENTAL_MODEL.md) |
| Word-by-word glossary | [TERMINOLOGY.md](TERMINOLOGY.md) |
| Flows & algorithms | [HOW_IT_WORKS.md](HOW_IT_WORKS.md) |
| HTTP / reference | [REFERENCE.md](REFERENCE.md) |
| FAQ | [FAQ.md](FAQ.md) |
| Python layout & identity | [python/STABILITY.md](python/STABILITY.md) |
| Golden path app | [python/docs/start/GOLDEN_PATH.md](python/docs/start/GOLDEN_PATH.md) |
| How-to encyclopedia | [python/docs/start/HOW_TO.md](python/docs/start/HOW_TO.md) |
| Errors | [python/docs/start/ERROR_HANDLING.md](python/docs/start/ERROR_HANDLING.md) |
| Extend without bloat | [LONGEVITY.md](LONGEVITY.md) · [EXTENSIONS.md](python/docs/start/EXTENSIONS.md) |
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Ops / verify | [OPERATIONAL.md](OPERATIONAL.md) |
| Public API freeze | [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) |

### Commands you will actually run

```bash
# from repo root
./verify.sh                 # law + layout + longevity + gate + rust + uxc_check
make test-python-gate       # freeze / interop
make longevity              # strata + import-weight rules
```

---

Phase 2: §§1–11 and §13 used to live in this file. They were mixed-mode (tutorial +
reference + explanation). Content was **moved**, not deleted — see the table above.
