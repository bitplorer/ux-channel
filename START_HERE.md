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

**Async:** `@ch.on async def …` is legal. Call `await ch.registry.async_dispatch(intent)`.  
`dispatch()` refuses async handlers — it will not nest an event loop.

**CEK (optional):** `pip install "ux-channel[cek]"` then `ChannelConfig.development(..., cek="require")`.  
Default remains `cek=off`. Channel stays the product; cek-host 0.1.3 is the Cap machine.

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
