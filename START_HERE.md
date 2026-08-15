# Start here — first-time users of ux-channel

**Audience:** engineers who have never used this library.  
**Promise:** every non-obvious assumption is written down.  
**Time:** 5 minutes to a running morph (`uxchannel create-app`); ~20–40 minutes for sections 1–8.

**In 5 minutes**

```bash
pip install "ux-channel[asgi]"
uxchannel create-app myapp
cd myapp && pip install -r requirements.txt
uvicorn app.main:app --reload
```

Click **+1**. That is Intent → Result → morph. Then come back here for why.

| You want… | Jump to |
|-----------|---------|
| The one idea | §1 |
| Words that matter | §2 |
| End-to-end loop | §3 |
| Security (caps) | §4 |
| Regions & HTML | §5 |
| State (session/client/db) | §6 |
| First working app | §7 |
| Design *why* | §8 |
| What lives where (code map) | §9 |
| Import rules | §10 |
| Mistakes we see | §11 |
| Deeper reading | §12 |

Related maps: [DOCS.md](DOCS.md) · [MENTAL_MODEL.md](MENTAL_MODEL.md) · [LONGEVITY.md](LONGEVITY.md) · [TERMINOLOGY.md](TERMINOLOGY.md)

---

## 1. What this library is (and is not)

### One sentence

**ux-channel** is a **server-driven UI protocol and host**: the browser sends a signed **Intent** `{ action, args, cap }`; the server runs an **action**, optionally re-renders **regions**, and returns a **Result** `{ ok, ops[], error? }` that the client applies to the DOM (morph, toast, navigate, …).

```text
  Human clicks button
        │
        ▼
  Intent { action, args, cap }     ◄── cap proves “this principal may do this action with these args”
        │
        ▼
  Host: verify cap → run handler → update state/regions
        │
        ▼
  Result { ok, ops[] }             ◄── ordered effects, not free-form HTML soup
        │
        ▼
  Client applies ops (morph #region, toast, push_url, …)
```

### What it *is*

| It is | Meaning |
|-------|---------|
| A **protocol** | Intent / Result / ops / error shape shared by peers (Python host, Rust peer, future clients) |
| A **trust model** | **Capabilities** (caps) bind action + args + optional principal; not “session cookie alone = all actions” |
| A **host runtime** | `Channel`, regions, action registry, hooks, state façade |
| A **wire option** | JSON always works; **CXB** is a compact binary upgrade for the same IR |
| Multi-caller | Humans (UI), agents (`agents(ch)`), MCP, islands — **same registry**, different doors |

### What it is *not*

| It is not | Do not assume |
|-----------|----------------|
| A full frontend framework | You still choose HTML / React / ux-dom / Jinja for markup |
| An ORM or database | `state().db` is **guards**, not storage you get for free |
| “Just REST CRUD” | The unit of work is **action + signed args**, not resource URLs alone |
| Client-authoritative business logic | The browser must not invent prices, balances, or durable truth |
| Multiplayer game netcode | Realtime/WebRTC is an **optional plane**, not the core loop |
| A second language runtime for Python apps | Rust is a **second implementation** of the same law, not required to ship a Python app |

### Two artifacts in the monorepo

| Artifact | Path | You need it if… |
|----------|------|------------------|
| **Python host** | `python/` | Building a real app (almost everyone) |
| **Rust crate** | `rust/` | Host+peer kernel/runtime, classic gate, `uxc_check`, interop |

**Law** (both must obey): `SPEC/` + `conformance/` golden vectors.  
If Python and Rust disagree, **vectors win**.

Architecture (EffectGraph, proofs, flow correlation, peer kernel) is documented in
[`SPEC/architecture/`](SPEC/architecture/README.md). Classic IR 0.1 clients stay on the floor.

---

## 2. Vocabulary (do not invent synonyms)

| Term | What it is | What it is **not** |
|------|------------|---------------------|
| **Intent** | Message: `{ action, args, cap?, form?, request_id? }` | A database row |
| **Action** | Named server function registered on the channel (`"Cart.add"`) | A React event handler alone |
| **Cap / capability** | Signed token: action + **args hash** + expiry (+ optional sub/scopes) | A login session by itself |
| **args_hash** | SHA-256 of **sorted compact JSON** of args (Rust-parity) | Hash of the whole HTTP body |
| **Result** | `{ ok, ops[], error?, meta? }` | Free HTML string as the only response type |
| **Op** | One ordered effect: morph, toast, navigate, set_attr, … | Random JS eval |
| **Region** | Server-owned UI fragment with a stable **uid** | A CSS “region” |
| **Morph** | Replace/patch DOM for a region (idiomorph-style) | Full page reload (unless you `navigate`) |
| **Channel** | App façade: boot, register actions/regions, mint controls, dispatch | The HTTP framework |
| **Registry** | Table of action name → handler + hooks + cap service | Flask blueprints |
| **Principal** | Who is acting (`user_id`, roles) for authz | The cap secret |
| **state()** | App façade over session / client / db **guards** | SQLAlchemy |
| **agents()** | Non-human tool façade into the **same** registry | A second Channel |
| **Wire** | Encode/decode Intent & Result (JSON / CXB) | ASGI server |
| **CXB** | Compact binary codec for the same IR | A different product protocol |
| **Plane** | Optional product layer (realtime, MCP, bridge) | Core IR |
| **Hook** | `before` / `after` on dispatch (policy, rate limit, audit) | Express middleware for static files |

Full glossary: [TERMINOLOGY.md](TERMINOLOGY.md).

---

## 3. The application loop (order of operations)

Every interactive feature follows this **order**. Skipping a step is how apps become insecure or confusing.

```text
1. boot          Channel.boot(app, config=…) or secret=…
2. define        @ch.region  +  @ch.on(…) handlers
3. mint control  ch.control(action, trust_…) → attrs / cap for the button
4. browser       user activates control → POST Intent (+ cap)
5. verify        registry checks cap (args must match hash), principal, hooks
6. run           handler body (may use state(), draft, external DB)
7. result        return Result / morph / toast / raise ActionError
8. after hooks   audit, limits finalize, …
9. client        apply ops[] to DOM
```

### Mental model of *time*

| When | What is true |
|------|----------------|
| **SSR / first HTML** | Regions paint with current server state; controls embed **fresh caps** |
| **Click** | Cap must still be valid; args in the Intent must match what was signed |
| **After Result** | DOM matches ops; durable truth is only what the server wrote |

### Two paths to the same registry

```text
Human:   button → Intent + cap → registry → Result
Agent:   agents(ch).dispatch / AgentRunner → same registry → Result
```

Agents do **not** get a shadow database of actions. They get a **policy/budget door** into the same table.

---

## 4. Capabilities (the part people under-assume)

### Why caps exist

If the client could call `Refund.run` with `{ "amount": 1 }` after you rendered a button for `{ "amount": 50 }`, the UI is theater.  
A **cap** seals: *this principal may run this action with these args until expiry*.

### What is signed (simplified)

```text
mint(action, args) → token
  includes: action name
            args_hash = sha256(compact_json_sorted(args))[:32 hex]   # Rust-parity
            exp / once / sub / scopes as configured
verify(token, action, args) → ok or CapError
  recomputes args_hash from the Intent’s args; mismatch ⇒ fail
```

**Implication you must not miss:** if the handler reads `product_id` from args, that value must be in the **signed** args (often via `ch.control(..., trust_product_id=...)`). Putting the price only in a hidden HTML field **without** putting it in signed args is a bug.

### API names (Python ↔ Rust)

| Concept | Python | Rust |
|---------|--------|------|
| Mint | `CapService.mint` / `registry.mint` / control helpers | `CapService::mint` |
| Verify | `CapService.verify` | `CapService::verify` |
| Hash args | `CapService.hash_args` | `hash_args` |
| Error | `CapError` | cap errors |

There is **no** public `CapService.sign` for this path — that word was retired to avoid confusion with ticket signing (`sign_push` / WebRTC tickets are different).

### Development vs production

| Mode | Typical choice |
|------|----------------|
| Local demo | `ChannelConfig.development(secret=…, allow_memory_stores=True)` |
| Production | Strong secret, durable nonce/idempotency stores (e.g. Redis), `require_cap=True` |

**Secret:** long random string; treat like a signing key. If it leaks, mint caps offline.

---

## 5. Regions, morph, and HTML

### Region

A **region** is a server function that returns HTML (or a value the renderer turns into HTML) for a **stable uid**. After an action, the host can re-run regions and emit **morph** ops so the client patches only those slots.

```text
@ch.region
def badge(ctx):
    ...
    return '<span data-channel-id="…">…</span>'
```

### Why not return a whole new page every time?

You can `navigate` when you mean full navigation. For in-place UI, **ops** keep the protocol stable and cache-friendly across peers.

### Control attrs

`ch.control(handler, trust_…)` produces attributes the client/runtime uses to build an Intent (action name, cap, sealed args).  
Day-1 apps often stringify those attrs onto a `<button>`. Production apps often feed them into **ux-dom** / your component system — the **protocol** stays the same.

### Scripts / body attrs

`ch.scripts()` / body helpers inject the client runtime needed to POST Intents and apply ops. Without them, buttons have caps but nothing speaks the wire.

---

## 6. State — three kinds (do not merge them in your head)

`from ux_channel import state` → `st = state(ch, …)`

| Kind | Lives | Use for | Not for |
|------|-------|---------|---------|
| **session** | Server draft / session store | Cart counts, wizard steps | Money ledgers |
| **client** | Browser-visible (allow-listed paths) | Theme, UI chrome | `amount`, roles, secrets |
| **db** | **Your** database | Durable business records | Pretending channel stores orders |

**Quantity / money:** load via foundations (`Quantity.from_store…`); never trust client paths for magnitudes.  
**RMW:** use store semantics / drafts carefully under concurrency (see host stores docs).

Power backends: `from ux_channel.host.stores import MemoryStateStore` (not on root).

---

## 7. First working app (copy-paste)

Requires: Python 3.10+, `fastapi`, `uvicorn` (or any supported host).

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ux_channel import Channel, ChannelConfig

app = FastAPI()
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",  # ≥32 chars in real apps
        allow_memory_stores=True,
    ),
)

@ch.region
def badge(ctx):
    n = ch.draft.get("n", 0) or 0
    return f'<span data-channel-id="badge">Cart ({n})</span>'

@ch.on(refresh=[badge], idempotent=False)
def add(product_id: str = "sku"):
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)

@app.get("/", response_class=HTMLResponse)
def index():
    attrs = ch.control(add, trust_product_id="sku").as_dict()
    attr_s = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return f"""<!doctype html>
<html>
<head>{ch.scripts()}</head>
<body {ch.body_attr_string()}>
  {ch.html(badge)}
  <button type="button" {attr_s}>Add</button>
</body>
</html>"""
```

**What you should observe**

1. Page loads with Cart (0).  
2. Click **Add** → Intent with cap → handler → region refresh → morph → Cart (1).  
3. Tampering with signed args without a new cap fails verification.

**Day-1 explicitly *not* required**

- Redis, WebRTC, MCP, agent_runtime  
- Hand-rolled `ActionRegistry` + `mount_channel` (boot does this)  
- CXB (JSON is enough)

More: [python/docs/start/GOLDEN_PATH.md](python/docs/start/GOLDEN_PATH.md) · [python/docs/start/HOW_TO.md](python/docs/start/HOW_TO.md)

---

## 8. Design choices (why it is this way)

| Choice | Why |
|--------|-----|
| **Intent → Result**, not “RPC returns HTML only” | Same IR for DOM, agents, hardware, second languages |
| **Caps over args**, not only session cookies | UI cannot escalate args; agents need the same seal |
| **Sorted compact JSON args_hash** | Cross-language parity (Python ↔ Rust) without ambiguous key order |
| **Ops list** | Ordered, inspectable effects; easy to log, test, and morph |
| **Regions** | Partial update without inventing a client store of truth |
| **Root = application surface only** | Power APIs stay in packages (`host.stores`, `agent_runtime`, …) so the library does not look like 200 peer concepts |
| **Hooks (before/after)** | Cross-cutting policy without forking Channel |
| **Optional planes** | Realtime/MCP/bridge do not load on `import ux_channel` |
| **Conformance vectors** | “Works on my machine” is not law; goldens are |
| **JSON floor + CXB upgrade** | Always interoperable; optimize when needed |

Permanence strata and anti-bloat doors: [LONGEVITY.md](LONGEVITY.md).

---

## 9. Implementation map (where truth lives)

### Monorepo

```text
SPEC/              IR / cap + SPEC/architecture/ (host/peer kernel)
conformance/       golden JSON + CXB + vectors/arch
python/src/ux_channel/   host library (you import this)
  arch/            HostRuntime, PeerApply, project, proofs
rust/              HostRuntime + PeerApply + classic Peer gate + uxc_check
verify.sh          law + both products
```

### Python packages (strata)

| Stratum | Packages | Role |
|---------|----------|------|
| L1 | `protocol` | Intent, Result, ops, CapService, error map |
| L2 | `host`, `render`, `security`, `api` | Channel, regions, HTML helpers, CSRF/limits |
| L3 | `wire`, `asgi`, `transport`, `redis_extra` | Codecs, HTTP mount, buses, Redis backends |
| L4 | `agent_runtime`, `mcp`, `bridge`, `realtime`, … | Optional product planes |
| L5 | `devtools`, `scaffold`, `catalog` | Audit, CLI, navigation catalog |

### Cold import (what loads when you `import ux_channel`)

**Loads:** protocol speech, Channel/registry, light HTML helpers, security surfaces.  
**Does not load:** wire/CXB, agent runner, MCP, WebRTC, encode/renderers until used.

This is intentional — first-time `import` should not pull the universe.

### Identity law

```python
from ux_channel import Channel, CapService, state
from ux_channel.api import Channel as C2, CapService as CS2, state as st2
# same objects — api is not a second implementation
```

---

## 10. Import rules (copy this into team norms)

```python
# Application (preferred)
from ux_channel import (
    Channel, ChannelConfig, Region,
    CapService, CapError,
    Intent, Result, morph, toast, navigate,
    state, agents, attach_audit,
)

# Same surface
from ux_channel.api import Channel, CapService, state

# Power (explicit packages)
from ux_channel.host.stores import MemoryStateStore
from ux_channel.host.testing import ChannelTest
from ux_channel.agent_runtime import AgentRunner, AgentPolicy
from ux_channel.wire import encode, encode_cxb
from ux_channel.asgi import mount_channel
from ux_channel.mcp import McpToolAdapter
```

| Do | Don’t |
|----|--------|
| Put new features behind hooks / stores / planes | Grow root `__all__` for every idea |
| Mint caps with the args the handler will see | Trust client-only fields for money/authz |
| Use `mint` language for caps | Expect `CapService.sign` for Intent caps |
| Read [EXTENSIONS.md](python/docs/start/EXTENSIONS.md) before adding packages | Create `day1/` style throwaway trees in the library |

---

## 11. Common mistakes (read before your first PR)

1. **Unsigned business args** — price/qty only in HTML, not in cap args.  
2. **Client path for money** — `st.client("amount")` is wrong by design.  
3. **Assuming root has everything** — `MemoryStateStore` / `ChannelTest` / `AgentRunner` are package imports.  
4. **Skipping scripts()** — caps without a client runtime look “broken.”  
5. **Treating Result as optional** — handlers should return Result/ops-friendly values; arbitrary dicts are not silently “ok.”  
6. **Using agents as a second app** — agents must hit the same actions humans do.  
7. **Changing IR without vectors** — if you touch Intent/Result/cap/CXB, add conformance.  
8. **Production with memory stores** — multi-worker will lie; use Redis (or your durable backends).  
9. **Short secrets** — cap signing is only as strong as the secret.  
10. **Confusing toast with logging** — `toast` is a **client op**; host logs use logging/audit.

---

## 12. Where to go next

| Path | Doc |
|------|-----|
| Mental model (short) | [MENTAL_MODEL.md](MENTAL_MODEL.md) |
| Word-by-word glossary | [TERMINOLOGY.md](TERMINOLOGY.md) |
| Flows & algorithms | [HOW_IT_WORKS.md](HOW_IT_WORKS.md) |
| HTTP / reference | [REFERENCE.md](REFERENCE.md) |
| FAQ | [FAQ.md](FAQ.md) |
| Python layout & identity | [python/STABILITY.md](python/STABILITY.md) |
| Golden path app | [python/docs/start/GOLDEN_PATH.md](python/docs/start/GOLDEN_PATH.md) |
| How-to encyclopedia | [python/docs/start/HOW_TO.md](python/docs/start/HOW_TO.md) |
| Errors | [python/docs/start/ERROR_HANDLING.md](python/docs/start/ERROR_HANDLING.md) |
| Extend without bloat | [LONGEVITY.md](LONGEVITY.md) · [EXTENSIONS.md](python/docs/start/EXTENSIONS.md) |
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Ops / verify | [OPERATIONAL.md](OPERATIONAL.md) |
| Public API freeze | [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) |

### Commands you will actually run

```bash
# from repo root
./verify.sh                 # law + layout + longevity + gate + rust + uxc_check
make test-python-gate       # freeze / interop
make longevity              # strata + import-weight rules
```

---

## 13. Checklist: “I understand enough to build”

- [ ] I can draw Intent → verify → action → Result → ops without notes  
- [ ] I know why **args_hash** exists and what happens if args change after mint  
- [ ] I know region vs full navigate  
- [ ] I know session vs client vs db state  
- [ ] I can boot a Channel and wire one button with `control`  
- [ ] I know what **not** to import from root  
- [ ] I know optional planes (agents, MCP, WebRTC) are doors, not the core loop  
- [ ] I know conformance vectors beat folklore  

When all boxes are checked, you are no longer a first-time user — build the product, and open [LONGEVITY.md](LONGEVITY.md) before adding a new package.
