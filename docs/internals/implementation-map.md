# Implementation map (where truth lives)

> **Diátaxis:** explanation · **Canonical:** `docs/internals/implementation-map.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 9. Implementation map (where truth lives)

### Monorepo

```text
SPEC/              IR / cap + SPEC/architecture/ (Channel façade over cek-runtime)
conformance/       golden JSON + CXB
python/src/ux_channel/   host library (you import this)
  host/            Channel, registry, regions
  cek/             CekHostCapService façade → cek-runtime Host
  protocol/        classic CapService (cek=off) + IR types
rust/              classic Peer gate (verify-only) + CXB + uxc_check
verify.sh          law + both products
```

The parallel `arch/` / `HostRuntime` / `PeerApply` plane was deleted
([ADR 0011](../../SPEC/architecture/ADR/0011-delete-parallel-arch-kernel-cut4.md)).

### Python packages (strata)

| Stratum | Packages | Role |
|---------|----------|------|
| L1 | `protocol` | Intent, Result, ops, CapService, error map |
| L2 | `host`, `render`, `security`, `api` | Channel, regions, HTML helpers, CSRF/limits |
| L2′ | `cek` | Cap façade to cek-runtime Host (default decide) |
| L3 | `wire`, `asgi`, `transport`, `redis_extra` | Codecs, HTTP mount, buses, Redis backends |
| L4 | `agent_runtime`, `mcp`, `bridge`, `realtime`, … | Optional product planes |
| L5 | `devtools`, `scaffold`, `catalog` | Audit, CLI, navigation catalog |

### Cold import (what loads when you `import ux_channel`)

**Loads:** protocol speech, Channel/registry, light HTML helpers, security surfaces.  
**Does not load:** wire/CXB, agent runner, MCP, WebRTC, encode/renderers until used.

This is intentional — first-time `import` should not pull the universe.

### Identity law

```python
from ux_channel import Channel, CapService, state
from ux_channel.api import Channel as C2, CapService as CS2, state as st2
# same objects — api is not a second implementation
```

---
