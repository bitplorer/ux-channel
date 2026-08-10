# I/O channel (not a driver)

**Constitution:** *uxchannel is the capability-shaped I/O channel for multi-actor mesh workplaces; drivers and protocols live in adapters.*

```text
Mesh is how envelopes travel.
Channel is how authority is shaped.
Adapters are how effects land.
```

## Status (roadmap)

| Phase | Item | Status |
|-------|------|--------|
| A1 | scan ≡ button ≡ agent | Demo + tests |
| A2 | party room claim + TTL | Demo + tests |
| A3 | lab flash + Quantity budget + audit | Demo + tests |
| B1 | ticket → `IoRoomClaim` | `claim_from_ticket_claims` |
| B2 | checked dispatch path | `run_checked` |
| B3 | docs recipes | this page + HOW_TO |
| C1–C3 | adapter package + contracts JSON | `ux_channel.io_adapters` |
| D1 | I/O audit tape | `IoAuditLog` / `attach_io_audit` |
| D3 | property tests | `test_io_channel_phases` |
| D4 | short soak | `scripts/io_channel_soak.py` |
| E | drivers in core | **never** |
| — | **Workplace** product façade | [WORKPLACE.md](WORKPLACE.md) |

## Laws

Import `IO_LAWS` / `IO_CONSTITUTION` from `ux_channel.io_channel`.

## Quick recipe — join room → claim → act

```python
from ux_channel.foundations.io_channel import (
    IoGate, claim_from_ticket_claims, run_checked, attach_io_audit,
)
from ux_channel.io_adapters import LightsAdapter
from ux_channel.foundations.quantity import Quantity

gate = IoGate()
lights = LightsAdapter()
gate.register(lights.describe())
audit = attach_io_audit(channel)  # optional

claim = claim_from_ticket_claims({
    "room": "party",
    "peer_id": "phone-1",
    "scopes": ["lights"],   # attenuated — no lab/admin
    "exp": ticket_exp_unix,
})

run_checked(gate, lights, "scene", ["party"], claim=claim, audit=audit)
```

## Quick recipe — event ≡ Intent

```python
payload = scanner.inject("SKU-100")  # fake hardware
args = gate.check_event(
    scanner.name, "scanned", payload,
    claim=pos_claim, method_for_keys="read",
)
# then agents(ch).dispatch("add_line", {"sku": args["sku"]})
# or the same @ch.on add_line as the button
```

## Quick recipe — budgeted command

```python
q = Quantity.from_store(1, "count", source="lab.policy.flash", revision=1)
run_checked(gate, lab, "flash", [], claim=lab_claim, quantity=q, audit=audit)
```

## Demo

```bash
PYTHONPATH=src uvicorn examples.io_mesh_workplace.app:app --host 0.0.0.0 --port 8080
```

See [examples/io_mesh_workplace/README.md](../examples/io_mesh_workplace/README.md).

## Reference adapters

| Adapter | Package path | Role |
|---------|--------------|------|
| Scanner | `ux_channel.io_adapters.ScannerAdapter` | POS scan events |
| Lights | `ux_channel.io_adapters.LightsAdapter` | Party-mode commands |
| Lab DUT | `ux_channel.io_adapters.LabDutAdapter` | Budgeted flash |
| Contract | `io_adapters/contracts/lab_dut.json` | JSON protocol |

## API map

| Symbol | Role |
|--------|------|
| `IoProtocol` / `IoMethodSpec` / `IoKind` | Sealed contract |
| `IoRoomClaim` | Mesh membership ≠ trust |
| `IoGate` | Policy check |
| `run_checked` | check → adapter.call → audit |
| `claim_from_ticket_claims` | Ticket/JWT mapping |
| `protocol_from_mapping` / `load_protocol_json` | Contracts |
| `IoAuditLog` | I/O policy tape |
| `IoAdapter` | Port **you** implement for real hardware |

Day-1 remains: `Channel` · `agents` · `state` · `attach_audit` · `webrtc`.
