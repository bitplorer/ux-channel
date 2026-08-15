<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Waves 1–5 — what is real in 0.1

This page is **honest about implementation depth**. Prefer this over older
roadmap claims. Core Intent → Action → Result is production-ready; wave extras
vary.

## Fully wired (use freely)

| Feature | API / notes |
|---------|-------------|
| Caps, CSRF header, origin | production defaults |
| Regions + `@ch.on` + `@Region.action` | refresh, multi-instance names |
| `ch.control` + `trust_*` | sealed args |
| Draft atomic `edit` / `change` / `merge` | façades over `ch.state` |
| SSE + WS auth (ticket / token / public.*) | same policy |
| Ticket revoke | `ch.revoke_ticket` |
| Navigate host allowlist | `navigate_allowed_hosts` / `with_navigate_hosts` |
| WS connect/message rate limits | configured on boot |
| Morph id stability | client copy + `ch.multi` wrap |
| WS reconnect resubscribe | tracks topics; resends `subscribe` on open |
| HTTP security events | `http_origin_deny`, `http_csrf_deny` |
| Redis backends (tested) | fakeredis suite `test_redis_backends` |
| `ch.live.bind` / `publish` | bind = in-process topic→regions map (**not** Redis sub); publish → PushBus |
| Region `state_get/set/change` | namespaced draft keys |
| Region `broadcast=` | fan-out after action |
| Policy on **actions** | `PolicyEngine.allow_action` + before-hook |
| Policy on **topics** | `allow_topic` enforced in `authorize_push_subscribe` |
| Tenant topic prefix | `tenant_topic_prefix` enforced for non-public topics |
| Security events | cap fail, push deny, WS origin/rate/connect/subscribe deny |
| Presence | `touch_presence` on WS subscribe; `ch.live.presence_*` |
| Redis optional backends | `redis_url=` / `config.redis_url` / `with_redis(url)` |
| `observe="otel"` | calls `attach_otel` if OpenTelemetry installed |

## Intentional limits (not incomplete — scoped)

| Feature | Reality |
|---------|---------|
| Progressive action SSE | Host returns **one** SSE chunk with final Result. `ResultStream` formats envelopes; multi-step generators are app-owned. |
| Idiomorph | Optional global; **not bundled**. Default is `replaceWith` + preserve `data-channel-id`. |
| `ch.action` vs `@ch.on` | Both exist; **prefer `@ch.on`**. `ch.action` is low-level registry. |
| TS codegen | Action **names** only; not full arg types. |
| Prometheus helper | Process-local counters unless you export them. |
| `meta.seq` on live publish | Stamped for operators/debug; client does **not** auto-resume (reconnect resubscribes). |

## Production recipe

```python
import os
from ux_channel import Channel, ChannelConfig

cfg = (
    ChannelConfig.production(os.environ["UX_CHANNEL_SECRET"])
    .with_navigate_hosts("myapp.com")
    .with_redis(os.environ["REDIS_URL"])  # multi-worker
)
ch = Channel.boot(app, config=cfg)  # uses config.redis_url

ch.live.bind("public.rates", "ticker")
# feeder:
ch.live.publish("public.rates")
```

## Tests

```bash
PYTHONPATH=src:. pytest -q tests/foundations/test_waves_all.py tests/asgi/test_integrity_wiring.py tests/redis_store/test_redis_backends.py tests/dx/test_next_production_path.py
```
