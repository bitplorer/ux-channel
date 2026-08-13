# Flow (default opt-in correlation)

## Definition

Multi-step work correlated by `meta.flow_id`. **Not** authority. **Not** a peer Flow engine.

## Config

```text
flow: "auto" | "off"
```

- `auto` (default): host flow helpers MAY set `meta.flow_id` / `meta.step`  
- `off`: host MUST NOT attach flow meta  

## Rules

1. Each step is still Intent + Cap.  
2. Peer applies `ops` whether or not `flow_id` is present.  
3. Unknown meta including `flow_id` MUST be ignored by peers that do not use it.  
4. Absence of `flow_id` means “not tagged”, not failure.  

## Host at will

- Call `flows.start` / `continue` / `complete` in handlers when product needs multi-step.  
- Single-step handlers omit flow meta.  

## Vectors

- `flow/meta-ignored`  
- `flow/step-cap-ok`  
- `flow/wrong-action-cap`  

## Assumptions

- Durable flow rows live in **app DB**, not peer kernel.  
- Resume is host re-emit of morph + fresh Caps.
