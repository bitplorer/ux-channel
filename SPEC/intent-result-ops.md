# Intent / Result / Ops — IR 0.1 (normative draft)

**Version label:** `"v": "1"`  
**Media types:**  
- `application/ux-channel+json` (required floor)  
- `application/ux-channel+cxb` (opt-in binary; see package `docs/core/CXB.md`)  

This document freezes the **semantic** contract. Byte layout of CXB is separate.

---

## 1. Intent

An Intent is a request to perform a named action under a capability.

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `v` | yes | string | Protocol major, currently `"1"` |
| `action` | yes | string | Dotted name, e.g. `Cart.add`, `Order.ship` |
| `args` | no | object | JSON-serializable; sealed subset is hashed into the cap |
| `cap` | conditional | string | Capability token; required when the action or channel policy demands it |
| `target` | no | string | Optional morph / region hint |
| `request_id` | no | string | Client correlation id (echoed in Result.meta when present) |
| `form` | no | object | Progressive-enhancement fields; must not override sealed trust args |
| `idempotency_key` | no | string | Optional dedupe key for declared-idempotent actions |

**Rules**
- Unknown top-level fields are ignored by receivers (forward-compatible).
- `action` is the primary routing key.
- Caps are verified *before* the action handler runs.

---

## 2. Result

A Result is the answer: success flag, ordered effects, optional error.

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `ok` | yes | boolean | Primary client branch |
| `ops` | no | array of Op | Ordered list of effects to apply; default `[]` |
| `error` | when `ok=false` | ErrorObject | Machine + human description |
| `meta` | no | object | `action`, `request_id`, `duration_ms`, `runtime`, … |
| `trace` | no | Trace | **Optional** causal spine (Phase 1.5) |

### ErrorObject

| Field | Required | Type |
|-------|----------|------|
| `code` | yes | string | `validation` \| `unauthorized` \| `not_found` \| `conflict` \| `internal` \| … |
| `message` | yes | string | Human-readable summary |
| `fields` | no | object | Field-level errors `{ "email": ["required"] }` |
| `retryable` | no | boolean | |
| `details` | no | any | Extra structured data |

**Rules**
- Clients branch on `ok` / `error.code`. HTTP status is secondary (derived for proxies).
- Partial success is expressed as `ok=true` + surviving ops + `meta.refresh_errors` (or similar) when applicable.
- `ops` are applied in order; a surface may stop on the first unrecognised op or continue per its policy.

---

## 3. Op (effect)

Every op is a JSON object with at least `"op": "<type>"`.

Common core ops (must be understood by any DOM surface):

| `op` | Purpose | Key fields |
|------|---------|------------|
| `morph` | Patch DOM at target | `target`, `html`, `morph?` |
| `swap` | outerHTML-style replace | `target`, `html`, `swap?`, `settle_ms?` |
| `remove` | Remove node | `target` |
| `set_attr` | Set attributes | `target`, `attrs` |
| `set_text` | Set text content | `target`, `text` |
| `toast` | User-visible message | `message` / `text`, `level?` |
| `navigate` | Hard navigation | `href` (unsafe schemes stripped) |
| `push_url` | History push | `href` |
| `reload` | Full reload | |
| `focus` / `scroll` | Focus / scroll control | `target` |
| `signal_set` | Client signal / store update | `name`, `value` |
| `clear_errors` | Clear field errors | |
| `noop` | Explicit no-op (with optional reason) | `reason?` |
| `bridge.*` | Bridge lifecycle | see bridge contract |
| `dispatch` | Client event | `name`, `detail?` |

**Extension rules**
- New op types are free strings.
- Dense CXB tags 1–63 are reserved for the common set; higher tags / free keys are for extensions.
- Surfaces that do not understand an op must either ignore it safely or refuse the Result with a clear error (never silent partial application of security-sensitive ops).

### Differential ops (optional, Phase 1.5)

When a surface has advertised support:

| `op` | Purpose |
|------|---------|
| `delta.patch` | JSON Patch / RFC 6902 style |
| `delta.crdt` | Compact CRDT fragment |
| `delta.signal` | Incremental signal update |
| `delta.remove` | Observed-remove / tombstone |

Full `morph` remains the universal fallback.

---

## 4. Optional Trace (causal spine)

```text
trace: {
  intent_id: string,          // stable ID of the originating Intent
  hops: Hop[],                // ordered, each peer-signed
  caused_by?: string          // parent intent_id for pipelines / fan-out
}

Hop {
  peer: string,
  at: timestamp,              // ISO or unix
  cap_fingerprint: string,    // attenuated cap that authorized this hop
  signature: bytes / string   // peer signs (intent_id + previous hop hash)
}
```

- Entirely optional.
- Caps may carry `max_hops` and `require_trace`.
- Used for audit, replay, and multi-peer debugging.
- JSON floor simply omits the field when not needed.

---

## 5. Versioning & compatibility

- `"v": "1"` is the current major.
- Additive optional fields and new op types are minor.
- Changing the meaning of an existing required field or reusing a dense CXB tag is a major break.
- Receivers must ignore unknown fields and unknown ops (or refuse safely).

---

## 6. Relation to other documents

- Binary encoding → package `docs/core/CXB.md`
- Capability tokens → [capability.md](capability.md)
- Causal / surface / delta design rationale → `../docs/archive/ux-channel-design-causal-surface.md`
- Wire multi-format surface → package `docs/core/WIRE.md`

---

**Exit criteria for this draft becoming final 0.1**
- Golden vectors exist for Intent / Result / common ops in both JSON and CXB.
- At least one non-Python decoder can round-trip the vectors.
- No required field changes after the 0.1 tag.
