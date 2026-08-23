# Implementation map (where truth lives)

> **Diátaxis:** explanation · **Canonical:** `docs/internals/implementation-map.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 9. Implementation map (where truth lives)

### Monorepo

```text
SPEC/              IR / cap + SPEC/architecture/ (host/peer kernel)
conformance/       golden JSON + CXB + vectors/arch
python/src/ux_channel/   host library (you import this)
  arch/            HostRuntime, PeerApply, project, proofs
rust/              HostRuntime + PeerApply + classic Peer gate + uxc_check
verify.sh          law + both products
```

### Python packages (strata)

| Stratum | Packages | Role |
|---------|----------|------|
| L1 | `protocol` | Intent, Result, ops, CapService, error map |
| L2 | `host`, `render`, `security`, `api` | Channel, regions, HTML helpers, CSRF/limits |
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
