# Enhance search demo

Self-contained page exercising Waves A\u2013C + handshake surfaces:

1. `ux-peer-kernel.js` \u2014 authority apply
2. `ux-peer-perception.js` \u2014 coalesce, shadow, pending
3. `ux-peer-continuations.js` \u2014 slot-fill on `timer.fired`
4. `ux-peer-dom-drivers.js` \u2014 real DOM shadow / pending / morph

Open `index.html` via any static server from repo root (relative script paths):

```bash
cd /path/to/ux-channel
python3 -m http.server 8765
# open http://127.0.0.1:8765/demos/enhance_search/
```

No backend required \u2014 host is simulated in-page.
