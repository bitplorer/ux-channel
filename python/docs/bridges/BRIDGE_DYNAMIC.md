<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# How “any npm package” stays knowable without FFI

## The real problem

| Wish | Reality |
|------|---------|
| Bridge auto-knows Chart.js methods | Chart.js is not importable from Python |
| One dynamic proxy for all npm | Every package has different constructors & lifecycles |
| Reflect TS types at runtime | Types erase; versions drift |

**You cannot safely auto-discover arbitrary npm APIs from ux-channel.**  
What you *can* do is make the **adapter** describe a **stable surface**.

## Resolution: adapter contract (not raw package)

```text
  npm package (chart.js)     ← huge, unstable surface
           │
           ▼
  adapter (your code)        ← small, intentional surface
           │
           ├── contract.json   (methods, args, mount_props)
           ├── mount/update/call/destroy
           └── uxBridge.register(package, adapter)
           │
           ▼
  Python ch.bridge.load_contract / call  ← validates against contract
```

**Dynamic on the wire:** method name + JSON args.  
**Known to Python:** only what the contract declares.

## Lifecycle is fixed; behavior is not

ux-bridge always uses the same lifecycle:

| Step | Op | Adapter |
|------|-----|---------|
| create | `bridge.mount` | `mount(el, props)` |
| patch | `bridge.update` | `update(handle, props)` |
| invoke | `bridge.call` | `call(handle, method, args)` |
| teardown | `bridge.destroy` | `destroy(handle)` |

Each package maps **into** that shape inside the adapter. That is how diversity is resolved — **not** by teaching Python every library.

## What is dynamic vs static

| Dynamic (runtime) | Static (contract) |
|-------------------|-------------------|
| Arg *values* (JSON) | Arg *shapes* (names, required) |
| Which method string is invoked | Which method strings exist |
| Props content | Required mount_props keys |
| Instance handle in browser only | Never on server |

## DX

```bash
uxchannel bridge new chartjs --npm chart.js --methods resetZoom,setData
# edit bridges/adapter-chartjs/contract.json  ← declare args
```

```python
ch.bridge.load_contract("bridges/adapter-chartjs/contract.json")
print(ch.bridge.describe("chartjs"))
# validate + emit
ch.bridge.call("c1", "setData", data={...}, package="chartjs")
```

## Optional: browser describe

Adapters may publish `uxBridge.contracts[package]` for devtools.  
Server truth remains `contract.json` loaded in Python (SSR, allowlists, CI).

## What we refuse

* Scraping `node_modules/**/*.d.ts` into Python at runtime  
* Treating `bridge.call("eval", ...)` as open without contract  
* Pretending LiveKit is a widget contract (`ch.media` instead)

## Summary

**Diversity of packages** → each has an adapter.  
**Diversity of methods** → each adapter’s `contract.json`.  
**Dynamic values** → JSON args on ops.  
**Stability** → contract version + allowlisted methods + action idempotency.
