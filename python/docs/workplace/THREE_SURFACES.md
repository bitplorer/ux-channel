# Three surfaces · one ceiling

**Button ≡ Agent ≡ Adapter event** — same `@ch.on` action, same caps/scopes.

```text
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  UI button   │   │ agents / wp  │   │  Adapter     │
│  wp.control  │   │  .dispatch   │   │  check_event │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │
       └────────────┬─────┴──────────────────┘
                    ▼
              Intent → Action → Result
                    ▲
              Workplace claim scopes
```

## Recipe

```python
from ux_channel.workplace import issue_mesh_membership, workplace_from_membership
from ux_channel.io_adapters import ScannerAdapter

mem = issue_mesh_membership(ch, "pos-desk", sub="clerk-1", scopes=["pos", "add", "scan"])
wp = workplace_from_membership(ch, mem).allow(ScannerAdapter())

@ch.on
def add_line(sku: str = ""):
    ...

# 1) Button
attrs = wp.control(add_line, trust_sku=sku).as_dict()

# 2) Agent
wp.dispatch("add_line", {"sku": sku})

# 3) Adapter event
payload = scanner.inject(sku)
args = wp.check_event("pos.scanner", "scanned", payload, method_for_keys="read")
wp.dispatch("add_line", {"sku": args["sku"]})
```

## Rules

1. **Server mints scopes** (`issue_mesh_membership` / `sign_workplace_ticket`) — never the browser.  
2. **Claim filters** tools, dispatch, and control.  
3. **Quantity** only via `Quantity.from_store` — not chrome.  
4. **RTC ticket** opens media; **workplace ticket** carries policy (or RTC + server scopes via `workplace_from_rtc`).  

## Demo

`examples/workplace_pos/` — prod-shaped POS with header CSRF, audit export, mesh membership.

See [WORKPLACE.md](WORKPLACE.md) · [WORKPLACE_OPS.md](WORKPLACE_OPS.md) · [IO_CHANNEL.md](IO_CHANNEL.md).
