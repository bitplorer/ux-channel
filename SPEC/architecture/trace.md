# Trace (CEK correlation)

## Definition

**trace** groups related Intents ([cek-framework VOCAB](https://github.com/bitplorer/cek-framework/blob/main/GLOSSARY.md)).
**Not** authority. **Not** a Cap. **Not** a peer Flow engine.

Wire-immortal alias: `meta.flow_id` maps to CEK `trace` (no wire break).
Channel encode: `flow_id` → `trace` (`cek/encode.py`).

## Config

```text
trace: "auto" | "off"     # primary speech (CEK VOCAB)
flow:  "auto" | "off"     # alias of trace (ChannelConfig.flow / env FLOW)
```

- `auto` (default): host MAY set `meta.trace` (and alias `meta.flow_id` / `meta.step`)
- `off`: host MUST NOT attach trace/flow meta

## Rules

1. Each step is still Intent + Cap.
2. Peer applies `ops` whether or not `trace` / `flow_id` is present.
3. Unknown meta including `trace` and `flow_id` MUST be ignored by peers that do not use them.
4. Absence of `trace` / `flow_id` means “not tagged”, not failure.

## Host at will

- Tag multi-step work with `meta.trace` (wire may still send `flow_id`).
- Single-step handlers omit trace meta.

## Vectors

- `flow/meta-ignored`
- `flow/step-cap-ok`
- `flow/wrong-action-cap`

(Vector path names stay; they are wire-era labels.)

## Assumptions

- Durable rows live in **app DB**, not peer kernel.
- Resume is host re-emit of morph + fresh Caps.
