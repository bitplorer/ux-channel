# Enhancement envelopes (Waves A–G) — additive only

**Status:** optional extensions on IR `"v": "1"`  
**Rule:** classic clients ignore unknown Result keys. Never required for interop.

## Result optional keys

| Key | Wave | Meaning |
|-----|------|---------|
| `continuations` | B | Pre-minted attenuated Caps + Intent templates for peer events |
| `trace` | E | Causal spine: intent_id + signed hops |
| `receipt` | later | Metering (reserved) |

## PeerHello (Wave D)

```json
{
  "ir_version": "1",
  "formats": ["json", "cxb"],
  "surfaces": ["dom.morph", "dom.toast", "delta.patch", "..."],
  "features": ["seq", "invoke", "perception.v1", "continuations"]
}
```

Default (no hello) = classic DOM surfaces only.

## Peer module separation (Wave C)

| File | Role |
|------|------|
| `ux-peer-kernel.js` | Authority apply only (ops, budget, proofs, queue) |
| `ux-peer-perception.js` | Perception IR only — attach via `uxcPerception.attach(kernel)` |
| `ux-peer-continuations.js` | Slot-fill for continuations — no Cap mint |

Perception must clear shadows before authority `applyResult`.

## Differential ops (Wave F)

`delta.patch` / `delta.signal` emitted only when peer advertised the surface.
Full `morph` remains universal fallback.

## Session recorder (Wave G)

Golden session files: `{ v, session_id, meta, events: [{kind, at, payload, peer?}] }`.
Replay against any peer of the same IR major.
