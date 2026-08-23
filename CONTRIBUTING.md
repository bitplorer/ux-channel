# Contributing

ux-channel is a **polyglot monorepo**: Python host (`python/`), Rust kernel (`rust/`),
SPEC + conformance vectors, JS static. Law is `SPEC/` + `conformance/`. If Python
and Rust disagree, **vectors win**.

Python-host details: [python/CONTRIBUTING.md](python/CONTRIBUTING.md).
Automation policy: [AUTOMATION.md](AUTOMATION.md).
Agent contract: [AGENTS.md](AGENTS.md).
Docs map: [docs/INDEX.md](docs/INDEX.md).

## Layer ownership

This repo owns Intent / Result / Capability / wire / peers / host runtime.
It does **not** own HTML trees or CSS. Do not add a document renderer here.

## Setup

```bash
# from monorepo root
python3 -m pip install -r requirements-dev.txt
export PYTHONPATH="$PWD/python/src${PYTHONPATH:+:$PYTHONPATH}"
```

Python 3.10+.

## Default workflow (automation first)

```bash
make sync-map          # packages ← disk, then regen catalog/map
make verify            # health + layout + longevity + law + gate + rust
```

| Do | Don't |
|----|--------|
| `make regen` / `make sync-map` | Hand-edit `catalog/catalog.json` or `modules` |
| Extend features in handlers / packages | Re-type module lists into docs |
| Update package `__init__.py` when role changes | Leave dead paths (`zones`, `day1`) as source of truth |
| Breaking IR only with `SPEC/BREAKING_CHANGE_POLICY.md` | Invent parallel RPC styles |
| Put new teaching in the matching Diátaxis slot | Mix tutorial steps into `REFERENCE.md` |

## What to hand-edit

- Action handlers, registry policy, cap/wire **logic**
- Package `__all__` (public API design) — freeze: [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md)
- Short Design / Architecture / Implementation in package `__init__.py`
- `SPEC/`, conformance vectors (law)
- `package_docs` / `strata` in `PACKAGE_MAP.json` when architecture labels change

Ceremonial outputs (`catalog/catalog.json`, derived `PACKAGE_MAP.json` fields) are
**regenerated**. Public export lists are hand design.

## Tests

```bash
make verify             # preferred
make test-python-gate   # freeze / interop
make test-python-host   # regions / state / core
make test-rust
./verify.sh --http      # + live peer
```

## Docs

| File | May contain | Must not contain |
|------|-------------|------------------|
| `README.md` | Gate only | Full API, ADR bodies |
| `START_HERE.md` | First success + vocabulary | Exhaustive encyclopedia (that is `python/docs/`) |
| `docs/INDEX.md` | Audience + Diátaxis routing | Duplicate of DOCS.md encyclopedia |
| `REFERENCE.md` / `SPEC/` | Facts | Learning narrative as primary form |
| `docs/archive/` | History | Current law |

Do not cite [docs/archive/](docs/archive/) as current teaching.

## Pull requests

- Feature branches. Never commit directly to `main`. Never force-push `main`.
- IR / cap / CXB changes require conformance vectors.
- Do not grow root `__all__` for every idea — power APIs stay in packages.
