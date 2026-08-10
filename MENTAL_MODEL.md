**First-time users:** read [START_HERE.md](START_HERE.md) first (this page is the short model).

# Mental model

## One sentence

The browser never invents business truth. It sends a signed **Intent**; the server runs an **action**, may update **regions**, and returns a **Result** of ordered **ops** the client applies.

```text
Browser                         Host (Channel)
───────                         ─────────────
control / form  ──Intent(+cap)──►  verify cap → action
DOM slots      ◄──Result(ops[])──  morph / toast / navigate / …
```

## Five strata

| # | Stratum | Owns | Does not own |
|---|---------|------|--------------|
| 0 | Wire IR | Intent, Result, ops, error codes | HTML, frameworks |
| 1 | Trust | CapService.mint / verify | Login UI |
| 2 | Host | Channel, actions, regions, state() | Markup |
| 3 | Render | morph HTML, placement, renderers | Business rules |
| 4 | Product | asgi, realtime, bridge, workplace… | Core IR |

## Application loop

```text
boot → region / on → control → runtime → draft / done|fail
```

## Monorepo

| Tree | Role |
|------|------|
| `SPEC/` + `conformance/` | Law + goldens |
| `rust/` | Peer: caps, CXB, Peer, `uxc_check` |
| `python/src/ux_channel/` | Full host library |
| `verify.sh` | health → layout → vectors → gate → rust → uxc_check |

## Package doors

| Intent | Package |
|--------|---------|
| App imports | `ux_channel` / `api` |
| IR + caps | `protocol` |
| Runtime | `host` (+ `stores` backends) |
| DOM output | `render` |
| Codecs | `wire` |
| HTTP mount | `asgi` |
| CSRF / limits | `security` |
| WebRTC | `realtime` |
| Widgets | `bridge` / `bridges` |
| Tooling | `devtools` |

## Confused pairs

| Term | Means |
|------|--------|
| toast | Wire **op** (user-visible notice), not a Python widget |
| state() | Application state API |
| stores | MemoryStateStore etc. |
| Region | One DOM slot |
| RegionBook | Registry of regions |
| mint / verify | Cap API (Rust-parity; not “sign”) |

## Ownership

```text
Channel owns: actions · caps · regions · Result ops · placement DATA
You own:      all HTML
```

See also [python/STABILITY.md](python/STABILITY.md), [python/ONTOLOGY.md](python/ONTOLOGY.md), [STRUCTURE.md](STRUCTURE.md), [NAMING.md](NAMING.md).


## Caller planes (who may invoke actions)

Channel is **one** registry of actions. Several **caller classes** may reach it.
They are not multiple Channels — they are different trust / budget doors.

| Plane | Package / entry | Principal | Trust model |
|-------|-----------------|-----------|-------------|
| **Human UI** | `Channel` + Intent + caps | End user | Short-lived caps, CSRF, control attrs |
| **Agent tools** | `agent_runtime (AgentRunner, peer)` | Agent / automation | Policy allow/deny, budgets, audit |
| **AX façade** | `agents(ch)` (`devtools.agents_api`) | Product API over runner/peer | Application speech only |
| **MCP transport** | `mcp` (uses `AgentRunner`) | MCP client | Same agent policy + session |
| **Island guest** | `bridge.guest_runtime` | Browser island | Sealed budgets; no durable quantities |
| **Workplace room** | `workplace` | Room member | Tickets / mesh membership |
| **Language peer** | `rust` peer | Wire peer | Caps + IR only (no full host) |

### What “runtime” means here

* **`agent_runtime`** — execution **kernel** for non-human tool calls (policy + session + runner).
* **`guest_runtime`** — sealed execution for **bridge islands** (under `bridge/`, not a sibling product plane).
* There is **no** `human_runtime` package: humans *are* the default Channel path.
* There is **no** generic `runtimes/` umbrella yet: caller classes differ in trust, not just folder cosmetics.

### When you would add another “runtime”

Only if a new **principal class** needs its own policy/budget/audit door into the same action registry, e.g.:

| Hypothetical | When justified |
|--------------|----------------|
| `batch_runtime` | Offline/job workers with distinct idempotency + rate law |
| `device_runtime` | Hardware/IoT principals with different cap attenuation |
| `partner_runtime` | External B2B callers with contract scopes |

Until then: **do not** invent `foo_runtime` for ordinary features — use Channel, workplace, or agent_runtime.

### Import rules

```python
# Humans (application)
from ux_channel import Channel, agents, state

# Agent kernel (power)
from ux_channel.agent_runtime import AgentRunner, AgentPolicy, AgentSession

# MCP (transport over kernel)
from ux_channel.mcp import McpToolAdapter

# Island guest (bridge)
from ux_channel.bridge.guest_runtime import GuestRuntime  # if exported
```

**Never** name a top-level package `agents` — it shadows the `agents()` function.
