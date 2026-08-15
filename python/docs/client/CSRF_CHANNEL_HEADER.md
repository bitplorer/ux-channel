<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# CSRF: channel vs host

## Channel CSRF (stable)

| | |
|--|--|
| Header | `X-Channel: 1` |
| Checked by | `security.channel_header_ok` when `require_channel_header=True` |
| Purpose | Cross-site classic form posts cannot set custom headers; our Intent client can |
| Not | Login, capability, or a token painted on ux-dom buttons |

```text
Intent POST → must include X-Channel: 1  (JSON)
Forms (urlencoded / multipart) → exempt (progressive enhance)
```

ux-dom / `ch.control(...).as_ux_dom()` only paints **action + cap + args**.  
No CSRF field on the button.

## Host CSRF (optional, any name)

Framework middleware may want *its* token under *its* header.  
uxchannel **does not validate** that. The client may **forward** it.

```js
// Preferred: tell the client exactly what your stack expects
window.__UX_CHANNEL_CSRF__ = {
  token: "…",
  headers: ["X-My-Middleware-CSRF"]
};
```

Or paint any meta/input whose name looks like csrf/xsrf; the client discovers it heuristically. Then it always sets `X-Channel: 1` **last**.

```python
from ux_channel.security.host_csrf import intent_headers, host_csrf_meta

intent_headers(host_token=tok, forward_as=("X-My-Middleware-CSRF",))
host_csrf_meta(tok, name="whatever-document-expects")
```

## Defaults

| Profile | `require_channel_header` |
|---------|--------------------------|
| production | `True` |
| development() | often `False` (curl demos) |

## Tests

* `tests/client/test_csrf_channel_header_chaos.py` — gate under load  
* `tests/client/test_host_csrf_agnostic.py` — any host header name  
* `tests/client/test_ux_dom_csrf_coexistence.py` — paint vs wire  

See [SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md) · [PRODUCTION_CHECKLIST.md](../production/PRODUCTION_CHECKLIST.md)
