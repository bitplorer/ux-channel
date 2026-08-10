# Patterns — uxchannel 0.1

| Pattern | How |
|---------|-----|
| Badge + button | Region + `@ch.on(refresh=[badge])` + `ch.control` |
| Sealed id | `trust_product_id=` on control |
| Optimistic toast | `ch.done(notice=…)` |
| Field errors | `ch.fail.valid({field: [msg]})` |
| One-shot pay | `once=True` + shared nonce store |
| Admin only | `auth=True, roles=["admin"]` |
| Multi-instance widgets | Class `Region` with distinct `uid` → `{uid}.method` |
| List filter | `ch.filter(list_region, q=…)` or `refresh` + scope `q` |
| Live ticker (no click) | `ch.live.bind` + `ch.live.publish` + client `push_topic` / WS |
