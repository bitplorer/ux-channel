# Naming constitution (ux-channel)

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |



## Laws

1. One name · one meaning · one call path
2. No alias map; no dual kwargs next to product names
3. Apps return `ch.done` / `ch.fail.*` only
4. Wire keys immortal (`ops`, `ok`, `error`, `data-channel-*`)
5. Markup strings only in `ux_channel.demo`
6. **AX** = `agents(ch)` only
7. **Quantity** = store-grounded measure (`magnitude` + `unit` + provenance)
8. **region** = morph paint surface (`@ch.region` and Morph IR `region(uid)`)
9. **I/O channel** = authorize I/O intents; **adapter** = perform I/O; never “driver” in core
10. **Workplace** = policy-shaped room (claim + gate + claim-aware agents)

## Preferred construction

```python
from ux_channel.quantity import Quantity

q = Quantity.from_store(10.5, "USD", source="db.order.9.amount", revision=3)
# builds Provenance internally — preferred over hand-built provenance
```

| Prefer | Rejected |
|--------|----------|
| `Quantity` | `Money`, `Authority` as the value type |
| `magnitude` + `unit` | `amount` + `currency` as type fields |
| `Quantity.from_store` | bare `Quantity(...)` without provenance |
| `QuantityBudget` | `RiskBudget` / `MoneyBudget` |
| `region(uid)` in IR | Morph region(uid) |

## Channel state kinds

| API | Kind |
|-----|------|
| `st.session` | Server draft chrome |
| `st.client` | Browser bag |
| `st.db` | Guards only — you own durable store |

```text
quantity → your durable store · chrome → session · theme → client
```

## Identity map (do not conflate)

| Concept | Name | Example |
|---------|------|---------|
| **Protocol version** (wire Intent/Result) | **`v`** | `"1"` |
| **Region identity** (Python) | **`Region.uid`** | `"cart.badge"` |
| **Region identity** (HTML) | **`data-channel-id`** | `cart.badge` |
| **Action→region bind** | **`region_uid`** (meta) | `"cart.badge"` |
| **Browser global** | **`uxChannel`** | `window.uxChannel.runAction` |
| **Client events** | **`channel:*`** | `channel:applied` |
| **Content-Type** | **`application/ux-channel+json`** | |

`v` is **never** a region id. Region ids never appear in the protocol version field.

