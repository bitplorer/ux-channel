# Property-based testing (Hypothesis)

## Why

Example tests prove **one story**.  
Property tests prove a **law** over a space of inputs — shrinking finds minimal counterexamples.

## Stack

```bash
pip install 'ux-channel[dev]'   # includes hypothesis>=6.100
pytest tests/foundations/test_properties.py -q
```

## Laws we encode

| Property | Module under test |
|----------|-------------------|
| Risky path segments always flagged | `path_is_risky` |
| Quantity dict roundtrip / session refuse | `Quantity`, `refuse_*` |
| Cap sign↔verify; attenuation never widens | `attenuate` |
| Envelope rejects foreign action/trust | `TreeEnvelope` |
| `stable_uid` deterministic | `slot_compile` |
| `tools_for` ⊆ registry; situation shape | `agents` (AX) |
| `effects.ok == result.ok` | `agents.effects` |
| Payment status machine | pay/refund/reset |
| Agent dispatch under `require_cap` | `agents(ch).dispatch` (foundation: `dispatch_peer`) |

## How to add a property

1. Name the **law** in plain language  
2. Write a `@given(...)` generator for the *interesting* space  
3. `assume(...)` to skip impossible cases  
4. Assert only the invariant (not a full scenario novel)  
5. Keep `max_examples` modest in CI; raise locally when hunting bugs  

## Not a good PBT target

* Full HTML morph layout  
* “UI looks nice”  
* “AX feels correct” without an invariant  
