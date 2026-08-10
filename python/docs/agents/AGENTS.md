# Agents (AX)

**AX** = Agent Experience. Application entry: **`agents(ch)`** only.

Foundations (Quantity, caps, Morph IR, peer impl) live in organic modules —
see [FOUNDATIONS.md](../foundations/FOUNDATIONS.md). They are **not** a second agent API.

```python
from ux_channel import agents

ag = agents(ch)
tools = ag.tools_for()
sit = ag.situation(facts={"step": "review"})
r = ag.dispatch("pay_order", {"order_id": "ord_1"}, peer=ag.peer("bot-1"))
fx = ag.effects(r)
```

| Method | Role |
|--------|------|
| `tools_for` | JSON-schema tools from the same registry as buttons |
| `situation` | World model for agents (not Morph `project_agent`) |
| `dispatch` | Same Intent path as humans |
| `effects` | Compact post-Intent summary |
| `peer` | Named peer for attribution |

Prefer `ag.dispatch` over importing `dispatch_peer` in app code.

Related: [API_SURFACE.md](../start/API_SURFACE.md) · [GOVERNING_STANCE.md](../start/GOVERNING_STANCE.md).
