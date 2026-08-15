<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Layers — where to import

> Feature encyclopedia: **[FEATURES.md](../FEATURES.md)**.


### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |



```text
  ux-dom / templates          markup only
        │
  Channel (application)            boot · region · on · control · done/fail
        │
  agents(ch)                 AX — tools · situation · dispatch · effects
  state(ch)                  session · client · db guards
  attach_audit(ch)           intent log + forensics
        │
  Foundations (by concern)
  quantity · provenance      store-grounded measures
  io_channel                 I/O channel (not driver) on mesh
  workplace/                 policy-shaped room (room · ticket · mesh)
  mcp/                      agent tools · effects · sessions · resources
  attenuate · tree_cap       capability nesting
  morph_ir · projections     multi-surface IR (elem, region)
  bridge_protocol · guest    sealed islands
  agent_runtime.peer         same-registry peer (prefer agents(ch))
```

## Prefer / avoid

| Prefer | Avoid |
|--------|--------|
| `from ux_channel.foundations.quantity import Quantity` | grab-bag imports |
| `ux_channel.io_channel` (gate + room claim) | device drivers in core |
| `Quantity.from_store(..., source=…, revision=…)` | bare numbers in session/client |
| `agents(ch).dispatch` | dual agent APIs |
| `from ux_channel.render.morph_ir import region` | Morph `slot` (removed) |
| `state(ch)` | teaching `planes()` as application |

## Public tiers

| Tier | Stability | Examples |
|------|-----------|----------|
| **Application public** | Frozen speech | `Channel`, `agents`, `state`, `attach_audit` |
| **Power public** | Stable; import by home | `Quantity`, `attenuate`, `morph_ir.elem` / `region` |
| **Internal** | May move | peer impl details, host plumbing |

See [API_SURFACE.md](API_SURFACE.md) · [FOUNDATIONS.md](../foundations/FOUNDATIONS.md) · [NAMING.md](NAMING.md).
