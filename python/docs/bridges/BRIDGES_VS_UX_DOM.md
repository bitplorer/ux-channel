# Bridges (ux-channel) vs widgets (ux-dom)

## Short answer

| Concern | Lives in |
|---------|----------|
| HTML / layout / canvas host | **ux-dom** |
| Signed controls, actions | **ux-channel** |
| npm island ops | **uxchannel `ch.bridge`** |
| Data façade (no Chart.js) | **`ChartBridge(ch)` factory / generated presets** |

## Day-1

```python
charts = ChartBridge(ch)
rev = charts("revenue", labels=…, values=…)
return rev.commit(values=[1, 2, 3])

spec = rev.mount_spec()   # ux-dom binds attrs
```

## Split

```text
ux-dom host  ←  mount_spec().attrs
     ↑
ChartBridge(ch)("id")  →  commit() → Result(ops=bridge.update…)
     ↑
Channel.boot(app)
```
