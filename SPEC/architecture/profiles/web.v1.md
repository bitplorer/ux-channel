# Profile web.v1

## Claim

```text
profiles: ["web.v1"]
```

## Methods / classic op mapping (drivers implement)

| Method / op | Args (informative) | Safety |
|-------------|-------------------|--------|
| morph | target, html | App encodes HTML |
| toast | message, level?, duration_ms? | |
| navigate | href, replace? | safeHref; skip if Result.ok === false |
| push_url | href, replace? | safeHref |
| reload | | skip if ok === false |
| focus | target, select? | |
| set_text | target, text | textContent semantics |
| dispatch | name, target?, detail? | CustomEvent-like |
| timer.set | id, ms, ops? | clamp ms; cancel on session gen |
| timer.clear | id | |

## Driver package

`drivers/web_v1` — **not** part of peer kernel.

## Assumptions

- DOM document exists.  
- Idiomorph optional; replace strategies documented in driver README.
