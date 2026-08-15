<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# ux-dom performance techniques (glue layer)

**Rule:** optimizations live in `ux_channel_ux_dom` — not inside `uxchannel` core.

## Principles

1. **Morph small regions** — never re-render the full page when one badge changes  
2. **Stable structure** — list keys → stable uids → cache-friendly  
3. **Cache compiles** — structure hash, not content hash  
4. **Dict trees on hot paths** — avoid duck-object walks when already dicts  
5. **Batch fragments** — many cards → one cache  

## API

```python
from ux_channel_ux_dom import inject_uids_cached, CompileCache, batch_inject

annotated, slots = inject_uids_cached(tree, prefix="cart")

cache = CompileCache(maxsize=512)
for fragment in cards:
    cache.inject(fragment, prefix="card")
```

## Measured wins (what to expect)

| Technique | When it helps |
|-----------|----------------|
| `inject_uids_cached` | Same layout, changing text/values |
| Region morph (channel) | Only paint dirty `data-channel-id` |
| `batch_inject` | Dashboards with N similar cards |
| Shallow dict | SSR paths already producing dicts |
| Avoid full `inject_ux_dom` stamp | Prefer IR → `paint_ux_dom_region` |

## Anti-patterns

* Walking entire ux-dom tree every click  
* New random uids per request (breaks morph + cache)  
* Mixing channel morph with full page HTML replace  
