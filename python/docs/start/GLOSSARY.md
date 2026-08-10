# Glossary — uxchannel 0.1

**Library version:** 0.1.0.

| Term | Definition |
|------|------------|
| **Action** | Server function registered with `@ch.on` or `@Region.action` |
| **AX** | Agent Experience — `agents(ch)`: tools_for, situation, dispatch, effects |
| **Workplace** | Policy-shaped room: claim + gate + claim-aware AX + I/O audit. Product form of I/O channel on mesh. |
| **I/O channel** | Capability-shaped authorization of I/O intents on mesh; **not** a device driver. See [IO_CHANNEL.md](../workplace/IO_CHANNEL.md). |
| **IoRoomClaim** | Mesh membership + attenuated scopes (+ optional expiry). Membership ≠ trust. |
| **IoAdapter** | Host-owned port that performs OS/hardware I/O after `IoGate.check`. |
| **Quantity** | Store-grounded measure: `magnitude` + `unit` + `provenance`. Prefer `Quantity.from_store(...)`. Never bare in client/session. |
| **QuantityBudget** | Ceiling on a quantity under a cap (`max_magnitude` + `unit`) |
| **Capability (cap)** | HMAC token binding action + args |
| **Channel** | Façade from `Channel.boot` |
| **Region** | Morph paint surface with stable `data-channel-id` |
| **Intent** | Client JSON invoking an action |
| **Op** | Apply instruction inside a Result |
| **Morph IR** | Host-agnostic tree (`elem` / `region`) |
| **Situation** | AX world model (`ag.situation`) |
| **Provenance** | Durable source stamp (`source`, `revision`, optional `principal`) |

