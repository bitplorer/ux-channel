# Python package structure

Canonical law: [STABILITY.md](STABILITY.md) · Automation: [../AUTOMATION.md](../AUTOMATION.md)

```text
src/ux_channel/
  protocol/ host/ render/ security/ api/     # core (hand design + tests)
  wire/ asgi/ transport/                     # adapters
  bridge/ bridges/ realtime/ …               # L4 planes (optional)
  devtools/ scaffold/ catalog/               # L5 tooling
  PACKAGE_MAP.json                           # packages intentional;
                                             # modules + count DERIVED
  catalog/catalog.json                       # GENERATED — make regen
```

Package `__init__.py` export lists are hand-maintained.  
Layout sync regenerates `catalog/` and derived map fields only.

```bash
make regen
make layout    # CI freshness
make verify
```
