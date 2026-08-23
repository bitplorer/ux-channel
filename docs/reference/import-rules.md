# Import rules

> **Diátaxis:** reference · **Canonical:** `docs/reference/import-rules.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 10. Import rules (copy this into team norms)

```python
# Application (preferred)
from ux_channel import (
    Channel, ChannelConfig, Region,
    CapService, CapError,
    Intent, Result, morph, toast, navigate,
    state, agents, attach_audit,
)

# Same surface
from ux_channel.api import Channel, CapService, state

# Power (explicit packages)
from ux_channel.host.stores import MemoryStateStore
from ux_channel.host.testing import ChannelTest
from ux_channel.agent_runtime import AgentRunner, AgentPolicy
from ux_channel.wire import encode, encode_cxb
from ux_channel.asgi import mount_channel
from ux_channel.mcp import McpToolAdapter
```

| Do | Don’t |
|----|--------|
| Put new features behind hooks / stores / planes | Grow root `__all__` for every idea |
| Mint caps with the args the handler will see | Trust client-only fields for money/authz |
| Use `mint` language for caps | Expect `CapService.sign` for Intent caps |
| Read [EXTENSIONS.md](../../python/docs/start/EXTENSIONS.md) before adding packages | Create `day1/` style throwaway trees in the library |

---
