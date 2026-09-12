<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Channel components — leftover kit teaching

Leftover: `ChannelComponent` / `components/` is **not Cap product**,
**not a sixth product**. Product UI is ux-dom + `ch.control`.
Do not port into compose `kit/`.

Optional leftover widgets under `ux_channel.components` (Counter, Flash, forms, …).

- Named **ChannelComponent** (not `Component`) to avoid ux-dom clashes  
- They use regions + actions under the hood  
- Prefer ux-dom + `ch.control` (or plain `@ch.region` + `@ch.on` when learning)

See leftover package `ux_channel.components` and examples under `examples/components_demo/`.
