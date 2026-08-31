<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# State — session · client · db

```python
from ux_channel import state
from ux_channel.foundations.quantity import Quantity

st = state(ch, allow=["ui.theme"])   # allow = client persist allowlist

n = st.session("n", 0)               # server draft chrome

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
