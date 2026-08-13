# Budgets

Default limits (implementations MAY tighten; MUST document if raised).

| Budget | Default | On exceed |
|--------|---------|-----------|
| max ops nodes | 256 | reject apply / reject emit |
| max seq depth | 16 | reject |
| max timer ms | 600000 | clamp or reject |
| max Result bytes | per runtime | reject |

**Vector:** `apply/budget`
