# uxchannel architecture — cohesion map

## Philosophy (non-negotiable)

1. **Channel is control plane, not a UI framework**  
   Intent → Action → Result(ops). HTML documents belong to ux-dom/templates/`ux_channel.render.kit`.

2. **One API per job**  
   Prefer a single application name; power layers stay off the façade teaching surface.

3. **Placement is data**  
   `attrs` + `client` + `scripts[]` — never HTML as the source of truth.

4. **Planes do not cross**  

   | Plane | Owns | Does not own |
   |-------|------|--------------|
   | Actions / regions | caps, morph, draft | video UI chrome |
   | `ch.media` | mesh tickets / SFU tokens | LiveKit media bytes |
   | `ch.bridge` | widget host + string ops | media SFU |
   | `ux-bridge.js` | adapter lifecycle | raw npm reflection |
   | OTel / DxLog | observe / CLI | business logic |

5. **Soft dependencies**  
   Redis, OTel, LiveKit SDK — optional; missing → warn, don’t crash core.

6. **Idempotent DX**  
   Contract method edits, OTel attach, CLI ops — re-run safe.

## Application surface (`CHANNEL_PUBLIC_API`)

```
boot · on · region · control · runtime · draft · done · fail · refresh
sign · diagnose · media · bridge · config · path
```

Everything else is power, demo, or import path (`ux_channel.webrtc`, `.otel`, `.scaffold`).

## Module map

```text
types / ops / encode     wire contract
registry / flow / caps   action engine
dx.Channel               façade
placement / media        placement bags
bridge_*                 npm widgets + contracts
html_document            runtime() + demo scripts/page attach
demo                     only HTML string adapters
trace + otel             forensics + optional distributed spans
dx_log + dx_errors       CLI observability
```

## Stability rules

* Additive ops OK; breaking wire → protocol version bump  
* `contract.json` `schema_version` for bridge adapters  
* Deprecate HTML helpers; do not re-teach them  
* Regression suite: `tests/core/test_capability_regression.py`
