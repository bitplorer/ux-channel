<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Cookbook — uxchannel 0.1

## Counter

```python
@ch.region
def counter(ctx):
    n = ch.draft.get("n", 0)
    return f'<span data-channel-id="counter">{n}</span>'

@ch.on(refresh=[counter])
def inc():
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
    return ch.done()
```

## Flash message region

```python
@ch.region
def flash(ctx):
    msg = ch.draft.get("flash") or ""
    ch.draft.clear("flash")
    return f'<div data-channel-id="flash">{msg}</div>'

@ch.on(refresh=[flash])
def save():
    ch.draft.set("flash", "Saved")
    return ch.done()
```

## Form with trust + validation

```python
@ch.on(name="Profile.save")
def save(email: str = ""):
    if "@" not in email:
        return ch.fail.valid({"email": ["Required"]}, message="Invalid")
    return ch.done(notice="Saved", refresh=["profile.card"])
```

Wire: `ch.control(save)` without trust for free-typed fields; use `trust_user_id=…` for sealed identity.

## Multi-region refresh

```python
@ch.on(refresh=["kpi.row", "chart.main", "flash.bar"])
def apply_filters(period: str = "7d"):
    ch.draft.set("period", period)
    return ch.done(notice=f"Period {period}")
```

## Call action from TestClient

```python
cap = ch.mint("inc", {})
r = client.post(
    "/ux-channel/action",
    json={"action": "inc", "args": {}, "cap": cap},
    headers={"X-UID-Channel": "1"},
)
```

## Live board (SSE)

```python
from ux_channel.transport.push import get_push_bus

result = ch.refresh("board.ticker", "board.rates")
get_push_bus().publish("sarrafa.board", result)
# HTML: ch.body_attr_string(push_topic="sarrafa.board")
```

See [SSE.md](../asgi/SSE.md).

