<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Bridge contract: how Python maps to npm JS

## Short answer

**There is no automatic mapping of Python functions to JS functions.**

| Side | What it knows |
|------|----------------|
| Python | Emits a **JSON op**: `{ "op": "bridge.call", "id", "package", "method", "args" }` |
| JS `ux-bridge.js` | Finds instance by `id`, runs **string** `method` on the adapter/handle |
| npm package | Your **adapter** implements `mount/update/call/destroy` and knows the real library |

Stability is a **named contract** (package key + method strings + wire version), not reflection.

```text
  Python action                         Browser
  ─────────────                         ───────
  ch.bridge.call(                       uxBridge.apply(op)
    "chart-1",                            → instances["chart-1"]
    "resetZoom",                          → adapter.call(handle, "resetZoom", args)
    package="chartjs",                        or handle.resetZoom(...args)
  )
       │
       │  Result.success / Result.ops  (JSON over HTTP/SSE/WS)
       ▼
  { op: "bridge.call", id: "chart-1",
    package: "chartjs", method: "resetZoom", args: [] }
```

---

## Lifecycle (who does what)

```text
1. npm adapter registered in the browser (once)
     uxBridge.register("chartjs", { mount, update, call?, destroy? })

2. Python places host data (not a live object)
     spec = ch.bridge.mount_spec("chart-1", package="chartjs", props={...})
     # your UI renders <div data-channel-bridge-id data-channel-bridge-package …>

3. Mount (idempotent-ish on client: destroy previous id then mount)
     ch.bridge.mount_ops("chart-1", "chartjs", props=...)

4. Later calls (by string)
     ch.bridge.call("chart-1", "resetZoom", package="chartjs")

5. Destroy
     ch.bridge.destroy_ops("chart-1")
```

Python **never** holds a Chart.js instance. It only holds **ids + JSON**.

---

## Who enforces stability?

| Concern | Enforcer | How |
|---------|----------|-----|
| Method allowlist | **Python** `BridgeManifest` | `ch.bridge.register("chartjs", methods=("resetZoom",))` then `call(..., package="chartjs")` raises if method unknown |
| Adapter present | **JS** runtime | Missing adapter → console warn, no throw (page stays up) |
| Method exists on instance | **JS** runtime | `adapter.call` or `handle[method]`; else warn |
| Wire shape | **Protocol version** `uid: "1"` + op names | Additive ops only without major bump |
| Idempotent **actions** | **Python** `@ch.on(idempotent=True)` + idempotency keys | Protects *server* re-POST; does **not** auto-dedupe client `bridge.call` |
| Idempotent **mount** | **JS** | Remount destroys previous instance for same `id` |
| npm API drift | **You** (adapter + tests) | Pin `chart.js@x` in app; adapter is the anti-corruption layer |

### What is NOT enforced today

* Automatic sync of TypeScript types ↔ Python  
* Exactly-once `bridge.call` if the client double-applies ops (use action idempotency + careful UI)  
* Server-side knowledge that JS actually ran the method (ops are commands, not RPC with return values on the default path)

---

## Idempotency: two different ideas

1. **Channel actions** (`@ch.on(idempotent=True)`)  
   Same Intent + Idempotency-Key → same Result (server).  
   Use this so “Reset chart” button double-clicks don’t double-charge side effects **on the server**.

2. **Bridge ops**  
   Client applies ops in order.  
   - `bridge.mount` for same `id` → dispose old, mount new (stable handle replacement).  
   - `bridge.call` is **not** automatically idempotent; calling `resetZoom` twice runs twice (usually fine).  
   - If a call is dangerous, gate it in the **Python action** (auth + idempotency), not in the adapter.

---

## Recommended stability pattern

```python
# startup — single source of method names (Python side)
CHART = "chartjs"
ch.bridge.register(CHART, methods=("resetZoom", "update", "destroy"))

# action
@ch.on(idempotent=True)
def reset_chart():
    return ch.done(*ch.bridge.call("main-chart", "resetZoom", package=CHART))
```

```js
// adapter — single source of method names (JS side)
uxBridge.register("chartjs", {
  mount(el, props) { return new Chart(el, props); },
  update(chart, props) { /* ... */ },
  call(chart, method, args) {
    if (method === "resetZoom" && chart.resetZoom) return chart.resetZoom(...args);
    if (typeof chart[method] === "function") return chart`method(...args)`;
    throw new Error("unknown method " + method);
  },
  destroy(chart) { chart.destroy(); },
});
```

**Keep method strings identical** in:
1. `ch.bridge.register(..., methods=(...))`  
2. adapter `call` switch / allowlist  
3. any TypeScript types you maintain in the app  

Optional later: generate both from one `contract.json` in `packages/@ux-channel/adapter-chartjs`.

---

## Mental model

```text
Python  ──commands (JSON ops)──►  ux-bridge  ──►  npm adapter  ──►  library
         not function handles      string names     your code        Chart.js etc.
```

Channels (HTTP/SSE/WS) carry **Result.success / Result.ops**. They do not open a bidirectional Python↔JS method channel with shared identity. That is intentional: simple, cacheable, SSR-friendly, and boring under load.

---

## Related

* [NPM.md](NPM.md) — where packages live  
* [BRIDGE_STRATEGY.md](BRIDGE_STRATEGY.md) — widgets vs media  
* [PLACEMENT.md](../start/PLACEMENT.md) — data not HTML  
