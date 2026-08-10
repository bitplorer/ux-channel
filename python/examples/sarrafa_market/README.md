# Sarrafa Market Tracker

Standalone **ux-dom + ux-channel** demo for an Indian **सर्राफ़ा** (bullion / jewellery) rate board.

## Features

- 24K / 22K / 18K gold + silver (₹/gram) with city premium
- Cities: Lucknow, Delhi, Mumbai, Jaipur, Kolkata, Chennai
- SVG sparkline history (no npm)
- Jewellery estimate: weight + making % + GST
- Live region morphs on every tick / city change

Rates are **simulated** for the demo — replace `tick_market` with your API/DB loader.

## Run

```bash
PYTHONPATH=src:/tmp/ux_dom \
  uvicorn examples.sarrafa_market.app:app --host 0.0.0.0 --port 8080
```

## Actions

| Action | Role |
|--------|------|
| `Market.tick` | Random-walk refresh |
| `Market.city` | City board (`trust_city`) |
| `Market.calc` | Recalculate estimate |
| `Market.reset` | Baseline board |
