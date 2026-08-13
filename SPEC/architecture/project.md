# Project

## Function

```text
project(graph, peer_hello, config) -> ops[]
```

**MUST** be pure (no I/O).

## Config

```text
effects: "auto" | "classic"
```

| Value | Behavior |
|-------|----------|
| `classic` | Emit only classic IR ops |
| `auto` | Emit richer forms when `peer_hello` supports them; else classic |

## Hello intersection

- If no profiles → classic only.  
- If profiles present → only methods in intersection.  
- Unsupported rich nodes → lower to classic equivalent when possible; else drop non-essential chrome per minimal policy.

**Vectors:** `project/classic-only`, `project/auto-web`
