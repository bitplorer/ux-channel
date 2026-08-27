# JS runtime

| Asset | Global | Role |
|-------|--------|------|
| `ux-channel.js` | `uxChannel` | Intent POST, morph, CSRF header, Signal→Intent (`data-channel-on`) |

## Signal → Intent

Triad: `data-channel-action` (WHAT) · `data-channel-on` (WHEN) · `data-channel-target` (WHERE).

Grammar examples:

```
data-channel-on="input delay:200"
data-channel-on="swipe.horizontal threshold:48"
data-channel-on="click swipe.left"
data-channel-on="longpress delay:500"
```

Modifiers bind to the preceding signal. Values: closest form → Intent.form. No client dual-bind store.

Catalog: click, change, input, blur, longpress, swipe.left/right/up/down; synthesizers swipe.horizontal/vertical; opt-out none.

Implements: `static/ux-channel.js`
