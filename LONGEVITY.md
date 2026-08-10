# Longevity — stable core vs moving parts vs anti-bloat

**Purpose:** keep the library usable for decades without becoming a monorepo junk drawer.  
**Companion:** [MENTAL_MODEL.md](MENTAL_MODEL.md) · [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 1. One sentence

**Law is eternal; the host is durable; product planes are optional; demos are disposable.**  
Bloat dies when new features must enter through **extension doors**, not root `__all__`.

---

## 2. Permanence strata (what may change)

```text
L0  LAW          SPEC + conformance + IR major     decades (change = major)
L1  PEER CORE    CapService, Intent/Result/ops, CXB tags, peer gate
L2  HOST CORE    Channel, Region, ActionRegistry, hooks, mint/verify path
L3  ADAPTERS     asgi, wire codecs, security CSRF, stores backends
L4  PLANES       agent_runtime, mcp, workplace, bridge, realtime, components
L5  TOOLING      devtools, scaffold, dashboard, profiling
L6  DEMOS        examples/, demos/, uxc_peer HTML
```

| Stratum | Stability promise | Examples |
|---------|-------------------|----------|
| **L0 Law** | Freeze on IR major; vectors are truth | `SPEC/`, `conformance/`, args_hash, op tags |
| **L1 Peer core** | Dual-language forever | `CapService.mint/verify`, `Intent`/`Result`, CXB decode |
| **L2 Host core** | App speech for years | `Channel.boot`, `@on`/`@region`, `control`, `done`/`fail`, `state()` |
| **L3 Adapters** | Stable *contracts*, swappable *impl* | FastAPI mount, Redis stores, wire formats |
| **L4 Planes** | May grow/split; never pollute L0–L2 | MCP, WebRTC, workplace, bridges |
| **L5 Tooling** | Free to churn | CLI, audit dashboards, codegen |
| **L6 Demos** | No production deps | examples |

**Rule:** if a change needs an IR major, it is L0/L1. If only Python apps care, it is L2+. If it is optional product chrome, it is L4+ and **must not** appear on root `__all__`.

---

## 3. Design choices already in place (keep them)

| Choice | Why it ages well |
|--------|------------------|
| Root = application surface only | Power stays in packages (`host.stores`, `agent_runtime`, …) |
| `api` ≡ root objects | One identity law |
| Rust peer shares law, not full host | Prevents dual hosts |
| `PACKAGE_MAP` v3 (`package.stem`) | Same short name, different planes |
| Conformance + `verify.sh` | Drift fails closed |
| Action **hooks** (`before`/`after`) | Cross-cutting without core forks |
| Wire **format plugins** | New codecs without core edits |
| Bridge **PluginHub** + entry points | Framework/renderer islands stay out of core |

---

## 4. Extension doors (the anti-bloat kit)

Do **not** invent a new top-level package for every feature. Force entry through one of these doors:

### Door A — Action hooks (middleware for Intent)

```text
Intent → before hooks → handler → after hooks → Result
```

| Use for | Not for |
|---------|---------|
| Authz policy, rate limit, audit, bulkhead, feature flags | New UI frameworks, new wire formats |

**API:** `registry.before(fn)` / `registry.after(fn)` (`host.hooks`).  
Hooks may short-circuit with a `Result` (before) or reshape `Result` (after).

### Door B — Store / backend protocols (swap persistence)

| Protocol-ish surface | Implementations |
|----------------------|-----------------|
| State / nonce / idempotency stores | Memory*, Redis* (`redis_extra`) |
| Push / RTC buses | Memory vs Redis |

New databases = **new backend modules**, not new Channel APIs.

### Door C — Wire format plugins

```python
# codec authors only
from ux_channel.wire.plugins import register_wire_format
```

Apps use `encode(..., format="cxb")` — never import plugin guts.

### Door D — Bridge / renderer plugins

```python
from ux_channel.bridge.plugins import get_hub
hub.add_renderer(...); hub.add_bridge_manifest(...)
# optional: entry point group ux_channel.plugins
```

Keeps Chart.js / ux-dom / Jinja out of L2.

### Door E — Caller planes (principals)

| Plane | Package | When |
|-------|---------|------|
| Human | Channel + caps | Default |
| Agent tools | `agent_runtime` | Non-human tools |
| MCP | `mcp` → AgentRunner | Transport |
| Island guest | `bridge.guest_runtime` | Sealed DOM islands |
| Workplace | `workplace` | Room tickets |

**New principal** ⇒ new plane package (or subpackage), **not** a root export.

### Door F — Host adapters (HTTP)

| Adapter | Package |
|---------|---------|
| FastAPI / Starlette | `asgi` |
| Future Django / Litestar | **separate installable** `ux-channel-django` style, not core bloat |

### Door G — Optional PyPI extras (distribution anti-bloat)

Recommended packaging shape (policy; evolve `pyproject` toward this):

```text
ux-channel                  # L1+L2+L3 thin: protocol, host, render, wire JSON, security
ux-channel[asgi]            # FastAPI mount
ux-channel[redis]           # redis_extra
ux-channel[realtime]        # webrtc/media
ux-channel[agents]          # agent_runtime + mcp
ux-channel[devtools]        # audit CLI dashboard
ux-channel[all]             # batteries
```

**Rule:** if a feature needs heavy deps (aiortc, redis, openai), it is an **extra** or a **sibling package**, never a hard core import.

---

## 5. Forever anti-bloat policy (checklist)

Before merging a feature, answer:

1. **Which stratum?** If L4–L6, it cannot touch L0–L2 public names without deprecation.  
2. **Which door?** Hooks / stores / wire plugin / bridge plugin / caller plane / adapter / extra.  
   If “none — just add to root”, **reject**.  
3. **Root `__all__`?** Default **no**. Application façade only (`PUBLIC_API_FREEZE`).  
4. **New package name?** Prefer subpackage under an existing plane (`agent_runtime.*`, `bridge.*`) over a new top-level word.  
5. **Dual language?** If wire/cap behavior changes, add a **conformance vector** first.  
6. **Demo?** Lives under `examples/` or `demos/` — zero imports from production packages into demos that create cycles.  
7. **Dep size?** New dependency ⇒ optional extra; core stays import-light.  
8. **Name collision?** Use `package.stem` map; never shadow root façades (`agents()`, `state()`).

### Hard freezes (decades)

| Frozen | Notes |
|--------|------|
| Intent / Result / error shape | IR major to break |
| Cap mint/verify + sorted `args_hash` | Rust parity |
| Op tag space for CXB | Append-only |
| Channel verbs: boot, on, region, control, done/fail, mint | Speech of the product |
| Hook pipeline order: before → handler → after | Documented semantics |

### Free to move

| Moving | Notes |
|--------|------|
| Dashboard UI, profiling, codegen | L5 |
| Bridge presets, chart adapters | L4 |
| WebRTC SFU details | L4 |
| Scaffold templates | L5 |
| Demo actions in Rust peer | L6 |
| Memory* default stores | Impl detail; protocol of stores is L3 |

---

## 6. Target architecture (mental picture)

```text
                    ┌──────────── L0 LAW ────────────┐
                    │  SPEC  ·  conformance vectors  │
                    └───────────────┬────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        L1 Python protocol    L1 Rust peer           (future peers)
              │                     │
              ▼                     │
        L2 Channel + Registry + Hooks ◄── Door A (before/after)
              │
       ┌──────┼──────────┬────────────┬────────────┐
       ▼      ▼          ▼            ▼            ▼
     L3     L3         L4           L4           L5
    asgi   wire      agent_runtime  bridge     devtools
   stores  security   mcp workplace realtime   scaffold
       │      │          │            │
       └──────┴──── Door B/C/D/E/F ───┘
```

---

## 7. Practical strategies (what to do next when growing)

| Pressure | Strategy |
|----------|----------|
| Root keeps growing | Gate test on `__all__` size + freeze list (already) |
| `host/channel.py` god module | Extract only behind stable façades; public methods stay |
| New vertical (e.g. payments agents) | Package under `agent_runtime` or `workplace`, not root |
| New HTTP framework | Sibling package via Door F + entry points |
| Optional heavy deps | `pyproject` extras (Door G) |
| Feature flags in core | Prefer before-hook feature gates over `if config` forests |
| Duplicate “audit” concepts | Keep names distinct (`devtools.audit` vs `agent_runtime.tool_audit`) |
| Docs sprawl | Day-to-day: MENTAL_MODEL + STABILITY; essays stay background |

---

## 8. What we will not do

- **No second Channel** (“ChannelV2”) without IR major and migration path  
- **No plugin system that bypasses caps** for mutating actions  
- **No** putting MCP/WebRTC/Redis imports in root `__init__`  
- **No** umbrella `runtimes/` package without a new principal class  
- **No** magic comments as API (`MANUAL_PUBLIC_API` removed)  

---

## 9. Summary table

| Want… | Put it… | Door |
|-------|---------|------|
| Change wire meaning | SPEC + vectors | L0 |
| New op type | protocol + CXB tag + both languages | L1 |
| Cross-cutting Intent policy | `registry.before/after` | A |
| New DB | store backend module | B |
| New codec | wire plugin | C |
| New UI island | bridge plugin | D |
| New caller class | caller plane package | E |
| New web framework | adapter package / extra | F |
| Heavy optional feature | extra or L4 plane | G |
| Tutorial app | examples/ | L6 |

**Longevity formula:** *stable grammar (Intent/Result/cap/hooks) + replaceable bodies (stores, adapters, planes) + empty root for everything else.*
