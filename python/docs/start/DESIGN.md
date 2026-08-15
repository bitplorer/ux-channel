<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Design constitution — uxchannel 0.1

**Library version:** 0.1.0 (brand **0.1**).

## One sentence

**Intent → Action → Result(ops)** with **signed capabilities** and **region morphs**.

## Closed product vocabulary

| Word | Meaning |
|------|---------|
| **Channel** | App façade (`Channel.boot`) |
| **Region** | Morphable SSR slot (`data-channel-id`) |
| **Action** | Named server handler (`@ch.on`) |
| **Control** | DOM wiring + capability (`ch.control`) |
| **Trust** | Server-sealed args (`trust_*`) |
| **Draft** | Ephemeral UI state (`ch.draft`) |
| **Op** | Client apply instruction (morph, toast, …) |
| **Bridge** | Optional npm widget host (not a region) |

## Rules

1. **ux-dom (or any HTML) owns trees.** Channel does not define buttons as widgets; it wires them.
2. **Caps carry ids and sealed args; loaders re-read truth** (DB / draft / state).
3. **One name per concept** — region not island (public API); refresh not revalidate (product speech).
4. **Fail closed** on caps, CSRF header (prod), unsafe hrefs.
5. **Async is real** — `async def` actions and hooks must actually run.
6. **RMW is explicit** — use `edit` / `change` / `merge`, not `get`+`set` pairs under concurrency.

## Layers

```text
Browser  --Intent+cap-->  ASGI host  -->  Registry  -->  Action
                ^                         | Result.success / Result.ops
                +------ apply ops --------+
```

## See also

[COURSE.md](COURSE.md) · [GLOSSARY.md](GLOSSARY.md) · [PRINCIPLES.md](PRINCIPLES.md) · [ARCHITECTURE.md](../foundations/ARCHITECTURE.md)

## Live plane

`ch.live.bind` is an in-process **topic → region** map for `publish`. Client subscribe and Redis push backend are separate layers.
