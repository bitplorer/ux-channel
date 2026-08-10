# Python host structure

**Mental model:** [../MENTAL_MODEL.md](../MENTAL_MODEL.md)  
**Layout law:** [STABILITY.md](STABILITY.md)  
**Monorepo map:** [../STRUCTURE.md](../STRUCTURE.md)  
**Ontology:** [ONTOLOGY.md](ONTOLOGY.md)

## Layout

```text
python/
  src/ux_channel/     package (src layout)
    api/ protocol/ host/ render/ security/ wire/ asgi/ …
    PACKAGE_MAP.json
  tests/gate/         CI interop + layout freeze
  tests/*             host suites
  docs/start/         application encyclopedia
  STABILITY.md LAYOUT.md ONTOLOGY.md README.md
```

## Permanent vs moving

| Permanent (IR / security / app speech) | Moving (power / demos) |
|----------------------------------------|-------------------------|
| `protocol` types, ops, CapService mint/verify | `render.kit` demos |
| `host.channel` Channel façade | dashboard plugins |
| regions core | bridge presets |
| `wire` codecs + CXB oracle | scaffold templates |
| root / `api` re-exports | workplace / mcp verticals |

## Forbidden (see STABILITY)

`day1`, `ops_dx`, `paint`, `zones`, `host` + old `dx` module, `CapService.sign`, `host/state.py` as stores module.
