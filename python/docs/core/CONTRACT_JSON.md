# contract.json — long-term shape

Single source of truth for one npm **adapter** surface (not the raw library).

## Canonical fields (`schema_version: 1`)

| Field | Role |
|-------|------|
| `schema_version` | Format version (integer). Bump only on breaking renames. |
| `package` | Adapter key (`data-channel-bridge-package`, `uxBridge.register`) |
| `version` | Adapter package semver (your release) |
| `npm` | Real npm package name (docs / peerDep hint) |
| `lifecycle` | Always `mount, update, call, destroy` (ux-bridge ops) |
| `methods` | **Map** name → method spec (never a list long-term) |
| `mount_props` | JSON-Schema-ish props for `bridge.mount` |
| `events` | Optional client event names (documentation / tooling) |
| `description` | Human blurb |

### Method spec

```json
{
  "name": "setData",
  "args": [{ "name": "data", "type": "object", "required": true }],
  "description": "…",
  "kwargs": true
}
```

* Key in `methods` **must** match `name`.
* `args` order = positional wire order when using kwargs expansion.
* `kwargs: true` → Python may pass a dict of named args.

## Idempotent CLI

```bash
uxchannel bridge add-method pkg foo          # added
uxchannel bridge add-method pkg foo          # unchanged (idempotent)
uxchannel bridge add-method pkg foo --arg x  # error unless --force
uxchannel bridge add-method pkg foo --arg x --force  # updated

uxchannel bridge remove-method pkg foo       # removed
uxchannel bridge remove-method pkg foo       # absent (idempotent)
```

Methods are a **dict** — you cannot get duplicates; re-add is merge/idempotent by fingerprint (name+args+kwargs+description).

## Stability rules

1. Never rename `package` lightly (breaks hosts + ops).  
2. Prefer additive methods; removing is a major for consumers.  
3. Keep lifecycle fixed — do not invent new lifecycle ops in contract.  
4. `normalize_contract()` rewrites files into canonical key order.  
5. Load with `ch.bridge.load_contract` so Python validation matches file.

## What is *not* in contract.json

* Full npm TypeScript surface  
* Secrets / TURN / media tokens (`ch.media`)  
* HTML templates  
