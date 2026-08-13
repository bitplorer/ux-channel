# Profile agent.v1

## Claim

```text
profiles: ["agent.v1"]
```

## Methods

| Method | Purpose |
|--------|---------|
| tool | Invoke local tool binding by name with args |
| log | Structured log line |

## Rules

- **MUST NOT** implement DOM morph as part of agent.v1.  
- Host SHOULD project agent-appropriate ops (no chrome-only morphs when only agent.v1 claimed).
