<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# CXB real-world benchmarks

> **Normative wire format:** see **[CXB.md](./CXB.md)** for complete layout, backends, and use cases.


Fixtures mirror production channel shapes (cart, auth, dashboard, bridges).
Rounds per timing cell: **150**.

## Size (bytes) & density

| Case | ops | JSON | msgpack | CXB | magic | vs JSON |
|------|----:|-----:|--------:|----:|-------|--------:|
| intent_cart_add | 0 | 244 | 195 | 192 | CXB1 | 1.27× |
| result_cart_toast_morph | 4 | 899 | 776 | 358 | CXBZ | 2.51× |
| result_login_fail | 4 | 443 | 336 | 314 | CXB1 | 1.41× |
| result_signup_validation | 2 | 472 | 383 | 373 | CXB1 | 1.27× |
| result_dashboard_refresh | 4 | 1165 | 1049 | 316 | CXBZ | 3.69× |
| result_multi_region_morph | 11 | 1319 | 1086 | 243 | CXBZ | 5.43× |
| result_nav_after_save | 3 | 185 | 134 | 125 | CXB1 | 1.48× |
| result_bridge_lifecycle | 4 | 330 | 255 | 231 | CXB1 | 1.43× |
| result_bulk_toasts | 40 | 2097 | 1559 | 102 | CXBZ | 20.56× |
| intent_search | 0 | 201 | 160 | 162 | CXB1 | 1.24× |

## Latency (µs) — encode / decode / round-trip

| Case | enc mean | enc p95 | dec mean | dec p95 | rt mean | rt p95 |
|------|---------:|--------:|---------:|--------:|--------:|-------:|
| intent_cart_add | 45.6 | 64.5 | 21.9 | 26.7 | 68.1 | 90.1 |
| result_cart_toast_morph | 122.1 | 146.6 | 56.4 | 74.5 | 190.4 | 212.7 |
| result_login_fail | 99.9 | 124.1 | 47.6 | 92.2 | 152.2 | 176.7 |
| result_signup_validation | 70.4 | 92.8 | 32.2 | 40.5 | 114.4 | 133.3 |
| result_dashboard_refresh | 124.8 | 149.4 | 53.2 | 70.7 | 192.2 | 216.5 |
| result_multi_region_morph | 225.8 | 252.5 | 112.1 | 136.9 | 349.3 | 388.2 |
| result_nav_after_save | 65.5 | 89.5 | 29.2 | 35.5 | 107.0 | 126.3 |
| result_bridge_lifecycle | 116.4 | 138.4 | 47.6 | 67.7 | 177.5 | 201.9 |
| result_bulk_toasts | 577.8 | 614.0 | 247.6 | 271.3 | 828.7 | 860.7 |
| intent_search | 32.5 | 41.4 | 15.3 | 20.3 | 56.1 | 75.6 |

## Reading

- **Cart / multi-region / bulk toasts** — CXB density shines (intern + tags + CXBZ).
- **Single intent** — smaller absolute sizes; JSON+orjson still fine for browsers.
- Latency is pure-Python CXB; network/RTT usually dominates over encode µs.

```bash
PYTHONPATH=src python scripts/bench_cxb_realworld.py --write docs/core/CXB_REALWORLD.md
```
