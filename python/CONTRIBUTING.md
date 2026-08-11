# Contributing to the Python host

Policy: **[AUTOMATION.md](../AUTOMATION.md)** — ceremonial outputs are regenerated;
hand-code only features, law, and public API.

## Setup

```bash
# from monorepo root
python3 -m pip install -r requirements-dev.txt
export PYTHONPATH="$PWD/python/src${PYTHONPATH:+:$PYTHONPATH}"
```

Python 3.10+.

## Default workflow (automation first)

```bash
# after adding modules under ux_channel/<pkg>/
make sync-map          # packages ← disk, then regen catalog/map
# or: make regen       # if packages inventory already correct

make verify            # health + layout + longevity + law + gate + rust
```

| Do | Don't |
|----|--------|
| `make regen` / `make sync-map` | Hand-edit `catalog/catalog.json` or `modules` |
| Extend features in handlers / packages | Re-type module lists into docs |
| Update package `__init__.py` Design/Architecture when role changes | Leave dead paths (`zones`, `day1`, sandbox zips) as “source of truth” |
| Breaking IR only with `SPEC/BREAKING_CHANGE_POLICY.md` | Invent parallel RPC styles |

## What to hand-edit

- Action handlers, registry policy, cap/wire **logic**
- Package `__all__` (public API design)
- Short Design / Architecture / Implementation in package `__init__.py`
- `SPEC/`, conformance vectors (law)
- `package_docs` / `strata` in `PACKAGE_MAP.json` when architecture labels change

## Tests

```bash
make test-python-gate   # CI path (interop + layout freeze)
make test-python-host   # regions / state / core
make test-python        # full suite (heavier; needs extras)
```

## Docs

- First-time: [../START_HERE.md](../START_HERE.md)
- Layout law: [STABILITY.md](STABILITY.md)
- Map: [../DOCS.md](../DOCS.md)
