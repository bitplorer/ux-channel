# Python host structure — permanent vs moving (stability)

**Purpose:** long-term clarity so contributors and users know what may change.  
**Concept map:** [ONTOLOGY.md](ONTOLOGY.md) · **Monorepo:** [../ARCHITECTURE.md](../ARCHITECTURE.md)

---

## Layout

```text
python/
  src/ux_channel/   ← package (src layout)
  ONTOLOGY.md           ← what things *are* (Region vs Bridge vs …)
  LAYOUT.md             ← every module mapped to a zone (anti-flat)
  STRUCTURE.md          ← this file (what may change)
  README.md
  ux_channel/zones/     ← navigational re-export hubs by intent
  docs/
    start/              ← day-1 layers, API surface, golden path
    regions/            ← region recipes
    core/               ← wire / CXB (shared law narrative)
  tests/                ← monorepo gate (must stay green)
  src/ux_channel/
    day1.py             ← preferred day-1 import façade
    __init__.py         ← full frozen root exports (__all__)
    … modules …
```

---

## Permanent (change only with IR major, security fix, or explicit deprecation)

| Area | Modules (representative) | Why permanent |
|------|--------------------------|---------------|
| Wire IR types | `types`, `ops`, `errors`, `error_map` | Shared language with Rust |
| Codecs | `wire/*`, encode helpers | Conformance vectors |
| Caps | `capability` (`sign`/`verify`, sorted `args_hash`) | Security interop law |
| Channel façade | `dx.Channel`, `config.ChannelConfig` | Day-1 speech |
| Regions core | `regions`, `region_component` | Product identity of host |
| Registry / context | `registry`, `context` | Action dispatch |
| HTML safety | `html_safe`, control attrs | XSS boundary |
| Day-1 exports | `day1.__all__`, root `__all__` names for day-1 symbols | User import contract |

**Gate:** `python/tests` + shared `conformance/` must pass (`make verify`).

---

## Stable power (may grow; avoid renames)

| Area | Modules | Notes |
|------|---------|-------|
| state / planes | `state_api`, `planes`, `ssr_state` | Prefer `state(ch)` day-1 |
| agents | `agents_api`, `agents/*` | Prefer `agents(ch)` |
| ASGI | `asgi/*` | Host adapters |
| morph_ir | `morph_ir` | Multi-surface IR |
| placement | `placement` | Framework-agnostic attrs |
| quantity / provenance | … | Domain foundations |

---

## Moving / optional (replace freely if permanent tests stay green)

| Area | Modules | Notes |
|------|---------|-------|
| bridges/* | Chart, Leaflet, … | npm islands; not core ontology |
| components/* | Badge, Modal kit | Optional; not required for Intent plane |
| region_directory, region_cli | FS discovery + scaffold | Shell features |
| demo, dx_dashboard | Demos | Not production contract |
| workplace, mcp, webrtc, … | Product planes | Grow independently |
| redis_extra | Optional stores | Extra install |

---

## Import policy (productivity + fewer bugs)

| Preference | Pattern |
|------------|---------|
| **New app code** | `from ux_channel.day1 import Channel, Region, …` |
| **Still OK** | `from ux_channel import Channel, Region` (same objects) |
| **Power features** | `from ux_channel.bridges import …` (by concern) |
| **Avoid** | Deep imports of private helpers; grab-bag `import *` from root in libraries |

**Rule:** if a symbol is not in `day1.__all__` and not documented in ONTOLOGY §3, treat it as power/internal until you read its module docstring.

---

## Bug-minimization rules (host)

1. **`render` is pure** — mutations only in actions.  
2. **`args_hash` always sorted compact JSON** — never swap engines.  
3. **Morph HTML must keep `data-channel-id`** — client replaceWith contract (tested).  
4. **Caps only server-side** — browser gets them via `ch.control` / signed attrs.  
5. **Do not advertise wire features the transport does not implement.**  
6. **Unknown refresh uids skip** — do not fail the whole Result.  
7. **Permanent tests live in `python/tests/`** — not only in the optional full suite zip.

---

## What we will not do (stability)

- Mass-rename 180 modules mid-0.1 without a major and migration guide.  
- Put production logic in `demos/`.  
- Make FastAPI a hard dependency of the core Intent/region plane (boot works without it).  
- Let CI go green on Rust alone.
