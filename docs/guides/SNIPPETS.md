# ux-channel — snippets

> **Diátaxis:** how-to · copy-paste patterns from the public API (`__all__` / CLI).
> Map: see this package `docs/INDEX.md`.

A click is a signed Intent. Caps authorize. Result carries ops.

Every block is meant to run (or to be the exact fragment you drop into a running app). Names are public exports. If code and this page disagree, **code wins**.

**17 snippets** covering install, core usage, fail-closed errors, live/async, CLI, and the usage patterns that keep layers from leaking.

### Public names in this cookbook

`FastAPI`, `HTMLResponse`, `Channel`, `ChannelConfig`, `morph`, `toast`, `navigate`, `swap`, `remove`, `set_text`, `set_attr`, `focus`, `scroll`, `http_status_for`, `Intent`, `Result`, `CapService`, `CapError`, `esc`, `mark_safe`, `user_content`, `SafeHtml`, `sel`, `uid_attr`, `create_channel`, `state`, `ERROR_HTTP_STATUS`

## Contents

- [Install + scaffold](#ch-install)
- [Boot, region, on, control, morph](#ch-core)
- [Result ops (morph, swap, toast, navigate)](#ch-ops)
- [Intent and Result (wire types)](#ch-intent-result)
- [CapService mint / verify](#ch-caps)
- [esc / mark_safe / user_content](#ch-esc)
- [ChannelConfig development vs production](#ch-config)
- [control() → ControlAttrs](#ch-control-attrs)
- [Result ops catalog](#ch-ops-full)
- [sel() / uid_attr() region helpers](#ch-sel)
- [create_channel factory](#ch-create)
- [state(ch) session / client / db](#ch-state)
- [ch.fail and error mapping](#ch-fail)
- [user_content / mark_safe / SafeHtml](#ch-user-content)
- [http_status_for + ERROR_HTTP_STATUS](#ch-http-status)
- [Async handlers](#ch-async)
- [Pattern: a click is a signed Intent](#ch-pattern-intent)


## Install

### Install + scaffold

<a id="ch-install"></a>

JSON is the floor. Caps authorize. Channel is the product; cek-runtime Host is the default Cap machine (`cek=require`). `cek=off` is the explicit escape.

```bash
pip install "ux-channel[asgi]"
pip install "ux-channel[cek]"    # default Cap machine (cek-host + cek-surface)
uxchannel create-app myapp
cd myapp && pip install -r requirements.txt
uvicorn app.main:app --reload
uxchannel doctor --fail
```


## Core usage

### Boot, region, on, control, morph

<a id="ch-core"></a>

Learn: boot, region, on, control, done/fail, morph/toast. Do not import ActionRegistry by hand on day 1.

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ux_channel import Channel, ChannelConfig, morph, toast

app = FastAPI()
ch = Channel.boot(
    app,
    config=ChannelConfig.development(secret="dev-" + "x" * 32),
)

@ch.region
def badge(ctx):
    n = ch.draft.get("n", 0) or 0
    return f'<span data-channel-id="badge">Cart ({n})</span>'

@ch.on(refresh=[badge], idempotent=False)
def add(product_id: str = "sku"):
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
    return ch.done()

@ch.on
def ping():
    return ch.done()

@app.get("/", response_class=HTMLResponse)
def index():
    attrs = ch.control(add, trust_product_id="sku").as_dict()
    attr_s = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return (
        "<!doctype html>"
        + "<html><head></head><body>"
        + ch.html(badge)
        + f'<button type="button" {attr_s}>Add</button>'
        + "</body></html>"
    )
```

### Result ops (morph, swap, toast, navigate)

<a id="ch-ops"></a>

Wire keys are immortal: op, target, html. Application code usually returns ch.done() / ch.fail().

```python
from ux_channel import morph, toast, navigate, swap, remove, set_text, set_attr, focus, scroll

ops = [
    morph("#cart", "<div id='cart'>1</div>"),
    toast("Added"),
    set_text("#count", "1"),
]
# In a handler, prefer ch.done() after draft.change, or return Result(ops=...)
```

### Intent and Result (wire types)

<a id="ch-intent-result"></a>

JSON is the floor. v is protocol version 1. Empty ops with ok=True is a valid no-op. Failures may still carry morph ops (re-render the form).

```python
from ux_channel import Intent, Result, morph, toast

intent = Intent(action="cart.add", args={"sku": "tee"}, cap=None)
print(intent.to_dict()["action"])

ok = Result.success(morph("#cart", "<div id='cart'>1</div>"), toast("Added"))
print(ok.ok, [op["op"] for op in ok.ops])

bad = Result.failure("invalid", "sku required", fields={"sku": ["required"]})
print(bad.ok, bad.error.code)
```

### CapService mint / verify

<a id="ch-caps"></a>

Caps bind action + args hash (+ optional principal). once=True requires a nonce store on verify. Do not ship development secrets.

```python
from ux_channel import CapService, CapError

caps = CapService(secret="dev-" + "x" * 32, max_age=900)
token = caps.mint("cart.add", {"sku": "tee"}, sub="user:42")
claims = caps.verify(token, "cart.add", {"sku": "tee"}, expected_sub="user:42")
print(claims["action"], claims["sub"])

try:
    caps.verify(token, "cart.checkout", {"sku": "tee"})
except CapError:
    print("action mismatch refused")
```

### esc / mark_safe / user_content

<a id="ch-esc"></a>

User-authored strings go through esc / user_content. mark_safe is an explicit hole; do not pass request data through it.

```python
from ux_channel import esc, mark_safe, user_content, SafeHtml

print(esc("<script>"))                 # escaped
print(user_content("hi <b>"))          # escaped inside a span
trusted = mark_safe("<b>ok</b>")
assert isinstance(trusted, SafeHtml)
print(esc(trusted))                    # not escaped — you opted in
```

### ChannelConfig development vs production

<a id="ch-config"></a>

development() generates a secret if omitted and allows memory stores. Do not ship it. Stolen-cap residual: shorter default TTL in production.

```python
from ux_channel import ChannelConfig

dev = ChannelConfig.development(secret="dev-" + "x" * 32)
print(dev.environment, dev.allow_memory_stores)

# Production: call production() (or construct + validate). Never reuse development().
# prod = ChannelConfig.production(secret=os.environ["CHANNEL_SECRET"])
```

### control() → ControlAttrs

<a id="ch-control-attrs"></a>

control() mints a Cap into the attrs when mint_cap=True (default). Trusted params: trust={...} or trust_<field>=.

```python
from fastapi import FastAPI
from ux_channel import Channel, ChannelConfig

app = FastAPI()
ch = Channel.boot(app, config=ChannelConfig.development(secret="dev-" + "x" * 32))

@ch.on
def add(sku: str = "tee"):
    return ch.done()

attrs = ch.control(add, trust_sku="tee")
print(attrs.as_dict())       # {"data-channel-action": "...", "data-channel-cap": "...", ...}
# button("Add", **attrs.as_dict())
# button("Add", **attrs.as_ux_dom())   # underscore keys some Python DSLs prefer
```

### Result ops catalog

<a id="ch-ops-full"></a>

Wire keys are immortal: op, target, html. Application handlers usually return ch.done() / ch.fail() rather than assembling this list by hand.

```python
from ux_channel import (
    morph, swap, toast, navigate, push_url, remove,
    set_text, set_attr, focus, scroll, reload, noop, clear_errors, signal_set,
)

ops = [
    morph("#cart", "<div id='cart'>1</div>"),
    swap("#panel", "<p>Hi</p>"),
    set_text("#count", "1"),
    set_attr("#save", "disabled", "true"),
    toast("Saved"),
    focus("#q"),
    scroll("#top"),
    navigate("/orders"),
    push_url("/orders"),
    clear_errors(),
    signal_set("cart", "1"),
    remove("#flash"),
    reload(),
    noop(),
]
print([op["op"] if isinstance(op, dict) else op for op in ops][:4])
```

### sel() / uid_attr() region helpers

<a id="ch-sel"></a>

Stable region identity is data-channel-id, not a CSS class you might restyle away.

```python
from ux_channel.host.channel import sel, uid_attr

print(sel("Cart:badge"))     # [data-channel-id="Cart:badge"]
print(uid_attr("Cart:badge"))
```

### create_channel factory

<a id="ch-create"></a>

Returns (ActionRegistry, PluginHub). Prefer Channel.boot on day 1. Production: ChannelConfig.from_env(), never development(secret=) in prod.

```python
from fastapi import FastAPI
from ux_channel import create_channel, ChannelConfig

app = FastAPI()
registry, hub = create_channel(
    config=ChannelConfig.development(secret="dev-" + "x" * 32),
    app=app,
    host="fastapi",
)
print(type(registry).__name__)
# Day-1 still prefers Channel.boot. create_channel is the factory when you
# already have a host and want ActionRegistry + PluginHub explicitly.
```

### state(ch) session / client / db

<a id="ch-state"></a>

state(ch) attaches ChannelState as ch.st. Not a database. Client persist is allowlist-only.

```python
from ux_channel import state

# After Channel.boot(...):
st = state(ch, allow=["ui.theme"])
n = st.session("n", 0)
# st.client  — client plane (strict by default; persist only allowlisted paths)
# st.db      — host-provided durable store facade, not a database
```


## Fail closed

### ch.fail and error mapping

<a id="ch-fail"></a>

Fail closed: unknown actions 404, illegal names 400. Do not swallow CapError.

```python
from ux_channel import http_status_for

@ch.on
def place(order_id: str = ""):
    if not order_id:
        return ch.fail("invalid", message="order_id required")
    return ch.done()

# http_status_for(error) maps protocol errors to HTTP for ASGI adapters
```

### user_content / mark_safe / SafeHtml

<a id="ch-user-content"></a>

Morph html= is caller-owned. esc / user_content for untrusted strings. mark_safe is an explicit trust boundary.

```python
from ux_channel import esc, user_content, mark_safe, SafeHtml

print(esc("<script>alert(1)</script>"))     # escaped
print(user_content("<b>raw</b>"))            # wrapped + escaped
trusted = mark_safe("<em>host-owned</em>")
assert isinstance(trusted, SafeHtml)
```

### http_status_for + ERROR_HTTP_STATUS

<a id="ch-http-status"></a>

Result body is the source of truth. HTTP status is a cache/proxy convenience. One mapping table for FastAPI / Starlette / batch.

```python
from ux_channel import Result, http_status_for, ERROR_HTTP_STATUS

ok = Result.success()
print(http_status_for(ok))                 # 200 even if ops are empty
bad = Result.failure("validation", "sku required")
print(http_status_for(bad))                # 422
print(ERROR_HTTP_STATUS["unauthorized"])   # 401
print(ERROR_HTTP_STATUS["rate_limited"])   # 429
```


## Live / async

### Async handlers

<a id="ch-async"></a>

Same rule as ux-behavior: sync dispatch never nests a loop.

```python
@ch.on
async def slow():
    # await work...
    return ch.done()

# Call:
# await ch.registry.async_dispatch(intent)
# dispatch() refuses async handlers — it will not start an event loop.
```


## Usage patterns

### Pattern: a click is a signed Intent

<a id="ch-pattern-intent"></a>

JSON is the floor. Caps authorize. Markup is the caller's (ux-dom / templates). Channel owns the wire.

```python
# Client never posts a free-form HTML patch.
# It posts Intent {action, args, cap}. Server returns Result {ok, ops[]}.
#
# 1. ch.control(add, trust_sku="tee") mints the Cap into button attrs
# 2. Browser runtime builds Intent from those attrs
# 3. Channel verifies Cap, runs the handler, returns Result
# 4. Runtime applies ops in order (morph, toast, …)
#
# Do not: fetch() a HTML partial and innerHTML it.
# Do not: skip Caps in production (require_cap=True).
# Do not: swallow CapError.
```
