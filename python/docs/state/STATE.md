<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# State — session · client · db

```python
from ux_channel import state
from ux_channel.foundations.quantity import Quantity

st = state(ch, allow=["ui.theme"])   # allow = client persist allowlist

n = st.session("n", 0)               # per visitor (the action's Cap subject)
hits = st.shared("hits", 0)          # one value for every visitor

@st.region
def badge(ctx):
    return f"<b>{n()}</b>"

@st.action
def inc():
    n.add(1)
    return st.done(refresh=["badge"])

st.client("ui.theme", "dark", persist=True)
st.db.guard(intent.args)

q = Quantity.from_store(
    order.amount, order.currency,
    source=f"db.order.{order.id}.amount",
    revision=order.version,
)
st.db.require(amount=float(q.magnitude))
```

## Who a session value belongs to

`st.session` is per visitor. Its key carries the subject of the verified
Cap of the running action (`ctx.verified.subject`), so mint each visitor's
Caps with `sub=` and resolve that visitor as the caller (`auth_resolver`).
ux-compose does both with its visitor cookie.

| Where | Read | Write |
|-------|------|-------|
| Action whose Cap has `sub=` | that subject's value | that subject's value |
| Page GET inside `reading_as(subject)` | that subject's value | `NoSessionSubject` |
| No subject (push render, Cap without `sub=`) | the default | `NoSessionSubject` |

`st.shared` is the explicit app-wide cell: every visitor reads and writes
the same value. Use it only for state that really is global.

## Rules

| Kind | Holds | Must not hold |
|------|--------|----------------|
| session | ids, steps, wizard chrome | `Quantity`, bare amounts on risky keys |
| client | theme, UI prefs (allowlisted) | durable quantity paths / `Quantity` type |
| db guards | validation only | your data — **you** load from store |

| Prefer | Avoid |
|--------|--------|
| `Quantity.from_store` after load | client `signal.set` of amounts |
| `st.db.guard` / `require` | trusting client-supplied magnitudes |

See [state-planes](../../../docs/reference/state-planes.md) · [FOUNDATIONS.md](../foundations/FOUNDATIONS.md).
