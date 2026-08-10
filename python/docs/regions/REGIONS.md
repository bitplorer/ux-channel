# Regions — uxchannel 0.1

A **region** is a morphable DOM slot identified by `data-channel-id`.

## Function style

```python
@ch.region
def cart_badge(ctx):
    n = ch.draft.get("n", 0)
    return f'<span data-channel-id="cart_badge">Cart ({n})</span>'

@ch.on(refresh=[cart_badge])
def add(product_id: str = "sku"):
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
    return ch.done(notice=f"Added {product_id}")
```

## Class style

```python
class CartBadge(Region):
    def render(self, ctx):
        n = self.ch.draft.get("n", 0)
        return f'<span data-channel-id="{self.uid}">Cart ({n})</span>'

    @Region.action
    def add(self, product_id: str = "sku"):
        with self.ch.draft.edit("n", default=0) as s:
            s.value += 1

badge = ch.use(CartBadge)
# actions: cart.badge.add  (uid.method)
# paint: badge() or badge.html(**scope) or ch.html(badge)
```

## Refresh behavior

- `ch.done(refresh=[…])` / decorator `refresh=` re-runs loaders and emits morph ops.
- **Unknown** region uids are skipped (warning).
- **Paint exceptions** on one region are skipped so other regions still update.

## Scope

```python
ch.html(badge, order_id="ord-1")
badge(order_id="ord-1")  # __call__ → html(**scope)
```

`ctx.scope` inside `render` holds those keys (plus principal-derived ids when present).

## Not regions

npm chart hosts use **bridges** (`mount_html`, `bridge_*` ops). See [PLUGINS.md](../bridges/PLUGINS.md).
