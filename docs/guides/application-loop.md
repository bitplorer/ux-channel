# The application loop (order of operations)

> **Diátaxis:** how-to · **Canonical:** `docs/guides/application-loop.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 3. The application loop (order of operations)

Every interactive feature follows this **order**. Skipping a step is how apps become insecure or confusing.

```text
1. boot          Channel.boot(app, config=…) or secret=…
2. define        @ch.region  +  @ch.on(…) handlers
3. mint control  ch.control(action, trust_…) → attrs / cap for the button
4. browser       user activates control → POST Intent (+ cap)
5. verify        registry checks cap (args must match hash), principal, hooks
6. run           handler body (may use state(), draft, external DB)
7. result        return Result / morph / toast / raise ActionError
8. after hooks   audit, limits finalize, …
9. client        apply ops[] to DOM
```

### Mental model of *time*

| When | What is true |
|------|----------------|
| **SSR / first HTML** | Regions paint with current server state; controls embed **fresh caps** |
| **Click** | Cap must still be valid; args in the Intent must match what was signed |
| **After Result** | DOM matches ops; durable truth is only what the server wrote |

### Two paths to the same registry

```text
Human:   button → Intent + cap → registry → Result
Agent:   agents(ch).dispatch / AgentRunner → same registry → Result
```

Agents do **not** get a shadow database of actions. They get a **policy/budget door** into the same table.

---
