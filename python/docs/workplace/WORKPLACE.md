<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Workplace — policy-shaped rooms

**Product form of the I/O channel course:** one room’s membership claim, sealed
adapters, claim-aware agents, and audit — without replacing application `Channel`.

```text
Channel     application: boot · region · on · control · done
Workplace   power: claim · gate · run_io · dispatch · situation
Adapters    your drivers (never in core)
```

## When to use

| Use Workplace | Stay on Channel alone |
|---------------|------------------------|
| Multi-actor mesh / rooms | Single-desk form app |
| Adapter I/O under scopes | Pure HTML morph UI |
| Agents filtered by ticket | Open internal tools |

## Boot

```python
from ux_channel import Channel, ChannelConfig
from ux_channel.workplace import workplace
from ux_channel.io_adapters import ScannerAdapter, LightsAdapter
from ux_channel.foundations.quantity import Quantity

ch = Channel.boot(app, config=ChannelConfig.development(secret="…", allow_memory_stores=True))

wp = workplace(
    ch,
    ticket={
        "room": "pos-desk",
        "peer_id": "clerk-1",
        "scopes": ["scan", "pos", "add"],
        # "exp": unix_ttl,
    },
).allow(ScannerAdapter(), LightsAdapter())
```

Or `workplace(ch, claim=claim_from_ticket_claims(jwt_claims))`.

## Surfaces

| API | Role |
|-----|------|
| `wp.dispatch(action, args)` | Same Intent path as buttons; **claim-filtered** |
| `wp.tools_for()` | AX tools this claim may use |
| `wp.situation(facts=…)` | World model + `workplace` snapshot |
| `wp.run_io(protocol, method, …)` | `run_checked` + I/O audit |
| `wp.check_event(…)` | Adapter event → Intent args |
| `wp.rebind(ticket=…)` / `wp.narrow(scopes)` | Membership / attenuate |
| `wp.snapshot()` / `wp.export_io_audit()` | Ops |

## Laws (inherited)

1. Mesh membership ≠ trust (`IoRoomClaim`)  
2. Caps/scopes attenuate only  
3. Chrome ≠ Quantity  
4. Adapters fail closed  
5. One mutation door (button ≡ agent ≡ `wp.dispatch` ≡ event→action)  
6. No drivers in core  

See [IO_CHANNEL.md](IO_CHANNEL.md) · [AGENTS.md](../agents/AGENTS.md) · [FOUNDATIONS.md](../foundations/FOUNDATIONS.md).

## Demo

```bash
PYTHONPATH=src uvicorn examples.io_mesh_workplace.app:app --host 0.0.0.0 --port 8080
```

## Import

```python
from ux_channel.workplace import Workplace, workplace, get_workplace
```

Power public — not re-exported on root (import by concern).

## Signed tickets (membership)

```python
from ux_channel.workplace import sign_workplace_ticket, workplace

tok = sign_workplace_ticket(
    ch.config, "pos-desk",
    sub="clerk-1",
    scopes=["pos", "add", "scan"],
    max_age=600,
)
wp = workplace(ch, ticket_token=tok)
```

* Browser **never** invents scopes — server mints tickets.
* WebRTC media tickets: `claim_from_rtc_ticket(config, rtc_tok, room, scopes=[...])`  
  (scopes from **your** policy, not the RTC payload).

## Claim-aware UI

```python
button_attrs = wp.control(add_line, trust_sku="SKU-100").as_dict()
# refuses actions outside claim; cap scopes ⊆ claim
```

Ops checklist: [WORKPLACE_OPS.md](WORKPLACE_OPS.md).  
Hardened demo: `examples/workplace_pos/`.

## Mesh membership (WebRTC + Workplace)

```python
from ux_channel.workplace import issue_mesh_membership, workplace_from_membership

mem = issue_mesh_membership(ch, "pos-desk", sub="clerk-1", scopes=["pos", "add", "scan"])
# mem.rtc_ticket       → browser WebRTC
# mem.workplace_ticket → policy
wp = workplace_from_membership(ch, mem)

# Or from an existing RTC ticket + server scopes:
# wp = workplace_from_rtc(ch, rtc_ticket, "pos-desk", scopes=["pos", "add"])
```

Three surfaces recipe: [THREE_SURFACES.md](THREE_SURFACES.md).  
0.1 freeze: [FREEZE_0.1.md](../start/FREEZE_0.1.md).

## Agents / MCP

Same room claim can mint MCP sessions — see [AGENTS_MCP.md](../agents/AGENTS_MCP.md).
