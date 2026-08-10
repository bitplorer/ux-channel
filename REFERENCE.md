# Reference — HTTP API, modules, recipes, extending

**Purpose:** Practical “how do I call this / where is the code / how do I add something?”  
**Not** the story (see [HOW_IT_WORKS.md](HOW_IT_WORKS.md)) or the glossary (see [TERMINOLOGY.md](TERMINOLOGY.md)).

---

## 1. Document map (everything in this package)

| Doc | Kind | Read when you need… |
|-----|------|---------------------|
| [TERMINOLOGY.md](TERMINOLOGY.md) | Guide | What a word **is / does / is not** |
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | Guide | Flows, order of steps, diagrams |
| [REFERENCE.md](REFERENCE.md) | Guide | **This file** — HTTP, curl, modules, recipes |
| [FAQ.md](FAQ.md) | Guide | Short answers to common confusions |
| [OPERATIONAL.md](OPERATIONAL.md) | Ops | Secrets, env, production checklist |
| [STRUCTURE.md](STRUCTURE.md) | Process | Law vs demo |
| [AGENTS.md](AGENTS.md) | Process | Agent checklist |
| [README.md](README.md) | Index | Status + verify |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Process | Monorepo layout + package boundaries |
| [CHANGELOG.md](CHANGELOG.md) | History | What landed in this tree |
| [SPEC/](SPEC/) | Law | Normative field rules |
| [conformance/](conformance/) | Law | Golden vectors + harnesses |
| [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) | Law | Host package public names |
| [ux-channel-*.md](ux-channel-roadmap.md) | Planning | Thesis / causal / roadmap (not law) |
| [rust/README.md](rust/README.md) | Peer | Rust build + HTTP notes |
| [demos/python_forward/README.md](demos/python_forward/README.md) | Peer | Tiny Python → Rust forward |
| [python/README.md](python/README.md) | Host | **Full Python library** (`ux_channel/`) |

---

## 2. HTTP API (Rust `uxc_peer`)

**Default bind:** `http://0.0.0.0:8787` (`UXC_HOST` / `UXC_PORT`).  
**Demo start:** `UXC_ALLOW_ORACLE_SECRET=1 cargo run --bin uxc_peer` (see OPERATIONAL).

### 2.1 `GET /ux-channel/health`

**Does:** Advertise what this process really supports today.

```bash
curl -sS http://127.0.0.1:8787/ux-channel/health | python3 -m json.tool
```

**Interesting fields:**

| Field | Meaning |
|-------|---------|
| `actions` | Demo action names |
| `formats` | HTTP codecs **served** (today: JSON only) |
| `codecs` | Library codecs (includes `cxb`) |
| `cap_required` | Actions that need a cap |
| `demo_mode` | Using public/allow-listed secret? |
| `policy.present_cap_must_verify` | Always true on this peer |
| `policy.once_jti_enforced` | `false` until once/jti lands |

### 2.2 `POST /ux-channel/mint` (dev)

**Does:** Mint a cap with the **same secret** the peer verifies.

```bash
curl -sS -X POST http://127.0.0.1:8787/ux-channel/mint \
  -H 'Content-Type: application/json' \
  -d '{"action":"Cart.add","args":{"sku":"abc-123","qty":2},"sub":"user:42","scopes":["cart:write"]}'
```

**Request fields:**

| Field | Required | Meaning |
|-------|----------|---------|
| `action` | no (default `Cart.add`) | Action name sealed into token |
| `args` | no (default `{}`) | Sealed args (hashed) |
| `sub` | no | Principal claim |
| `scopes` | no | Scope list |

**Success body:** `{ "ok": true, "cap": "<token>", "action": "...", "args": {...} }`  
**Protect in production** (firewall, auth, or disable).

### 2.3 `POST /ux-channel/action` (main product path)

**Does:** Intent → (cap gate) → action → Result.

```bash
# 1) mint
CAP=$(curl -sS -X POST http://127.0.0.1:8787/ux-channel/mint \
  -H 'Content-Type: application/json' \
  -d '{"action":"Cart.add","args":{"sku":"abc-123","qty":2}}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["cap"])')

# 2) action
curl -sS -D- -X POST http://127.0.0.1:8787/ux-channel/action \
  -H 'Content-Type: application/ux-channel+json' \
  -H 'Accept: application/ux-channel+json' \
  -d "{\"v\":\"1\",\"action\":\"Cart.add\",\"args\":{\"sku\":\"abc-123\",\"qty\":2},\"cap\":\"$CAP\",\"request_id\":\"demo-1\"}"
```

**Intent (request body):**

```json
{
  "v": "1",
  "action": "Cart.add",
  "args": { "sku": "abc-123", "qty": 2 },
  "cap": "<token>",
  "request_id": "optional"
}
```

**Result (response body) — success:**

```json
{
  "ok": true,
  "ops": [
    { "op": "toast", "message": "Added 2 x abc-123", "level": "success" },
    { "op": "morph", "target": "#cart", "html": "..." },
    { "op": "signal_set", "name": "cart.last_sku", "value": "abc-123" }
  ],
  "meta": { "action": "Cart.add", "peer": "ux_channel_rs", "runtime": "ux_channel_rs", "request_id": "demo-1" }
}
```

**Result — missing cap:**

```json
{
  "ok": false,
  "ops": [],
  "error": { "code": "unauthorized", "message": "capability token required", "retryable": false },
  "meta": { "action": "Cart.add", "runtime": "ux_channel_rs" }
}
```

HTTP status: `200` if `ok`, `401` if `unauthorized`, else `400` for Result errors.

### 2.4 Open action example (Counter)

```bash
curl -sS -X POST http://127.0.0.1:8787/ux-channel/action \
  -H 'Content-Type: application/ux-channel+json' \
  -d '{"v":"1","action":"Counter.inc","args":{"by":1}}'
```

No cap required **unless** you send a `cap` field (then it must verify).

### 2.5 Other routes

| Method | Path | Does |
|--------|------|------|
| `GET` | `/` | Interactive demo HTML page |
| `OPTIONS` | `*` | CORS preflight |
| other | — | Result-shaped `not_found` + HTTP 404 |

### 2.6 What HTTP does **not** do yet

| Feature | Status |
|---------|--------|
| `Accept: application/ux-channel+cxb` response | Library only; not negotiated |
| Request body CXB Intent | Not accepted on `/action` yet |
| once/jti single-use enforcement | SPEC gap |

---

## 3. Error cookbook (Intent → what you see)

| You send | You get `error.code` | HTTP | Why |
|----------|----------------------|------|-----|
| `Cart.add` without `cap` | `unauthorized` | 401 | Cap required |
| Bogus `cap` on any action | `unauthorized` | 401 | Present-cap-must-verify / bad signature |
| Cap minted for different args | `unauthorized` | 401 | args_hash mismatch |
| `"qty": "2"` (string) | `validation` | 400 | No silent coercion |
| `"v": "2"` | `validation` | 400 | Wrong IR major |
| `"action": "Nope.x"` | `not_found` | 400 | Unknown handler |
| Truncated / invalid JSON | `validation` | 400 | Wire fail still Result-shaped |

---

## 4. Module map (Rust peer)

```text
rust/src/
  lib.rs          crate root + re-exports
  types.rs        Intent, ResultDoc, Op, ErrorObject, Trace  [PERMANENT]
  wire_json.rs    JSON encode/decode + canonical JSON        [PERMANENT]
  cap.rs          mint/verify (itsdangerous-compatible)      [PERMANENT API]
  cxb.rs          CXB1/CXBZ encode/decode                    [PERMANENT tags]
  op_tags.rs      dense op field tags 1–63                   [PERMANENT]
  peer.rs         validate → cap gate → dispatch             [PERMANENT gate]
  actions.rs      Cart / Counter demo handlers               [MOVING]
  bin/uxc_peer.rs HTTP transport + demo HTML                 [MOVING]
  bin/uxc_check.rs conformance runner                        [MOVING surface, permanent duty]
```

| Call path | Functions |
|-----------|-----------|
| Bytes in → Result bytes | `Peer::handle_json` |
| Already-parsed Intent | `Peer::handle_intent` |
| Domain only | `actions::dispatch` |
| Cap only | `CapService::mint` / `verify` |
| CXB only | `encode_cxb` / `decode_cxb` / `is_cxb` |

---

## 5. How to add a new demo action (moving)

1. **Handler** in `actions.rs`: parse args strictly; return `ResultDoc` with ops or `validation` error.  
2. **Dispatch** arm in `actions::dispatch` match.  
3. If cap-required: add name to `CAP_REQUIRED` in `peer.rs`.  
4. **Health** list in `uxc_peer` `actions` array.  
5. **Tests:** unit test in `actions` or `peer`; optionally a peer edge in `uxc_check`.  
6. **Do not** change SPEC/vectors unless the new behavior is permanent law.  
7. Run `./verify.sh`.

Caps still run in `peer` — **never** reimplement verify inside the handler.

---

## 6. Conformance vector catalog

| Group | Files | What they prove |
|-------|-------|-----------------|
| Intent | `01-minimal` … `04-unknown-fields` | Smallest valid Intent; request_id; cap placeholder; unknown fields ignored |
| Result | `01-ok-morph` … `07-ok-multi-ops` | Success ops shapes; `unauthorized` / `validation` errors; navigate; multi-ops |
| Cap | `01-valid-notes.md`, `02-oracle-token.json` | Algorithm notes + concrete oracle token |
| Trace | `01`–`03` | Optional causal spine; missing trace still valid |
| Handshake | `01-surface-hello` | Optional surface advertisement (Phase 1.5+) |
| CXB expected | `expected/cxb/*` (14 blobs) | Decode interop with Python oracle |

Index: `conformance/manifest.json`.  
Run: `./verify.sh` or harness scripts in `conformance/harness/`.

---

## 7. Python code locations

| Path | What |
|------|------|
| [`python/src/ux_channel/`](python/src/ux_channel/) | Full host library (wire, capability, ASGI, …) |
| [`python/docs/core/`](python/docs/core/) | WIRE.md, CXB.md |
| [`demos/python_forward/forward_to_rust.py`](demos/python_forward/forward_to_rust.py) | Thin Intent POST client |
| [`conformance/harness/*.py`](conformance/harness/) | Vector validators |

See [`python/README.md`](python/README.md).

## 8. Python forward (recipe)

```bash
# peer must be up with allow-listed oracle for demo
UXC_ALLOW_ORACLE_SECRET=1 UXC_PORT=8787 cargo run --bin uxc_peer

# mint via peer (no itsdangerous required on host)
python3 demos/python_forward/forward_to_rust.py --mint-via-peer --sku abc-123 --qty 2
```

| Flag | Does |
|------|------|
| `--base URL` | Peer base (default `http://127.0.0.1:8787`) |
| `--mint-via-peer` | `POST /ux-channel/mint` instead of local itsdangerous |
| `--sku` / `--qty` | Sealed Cart.add args |

Exit `0` only if `result.ok`. Ops are printed unchanged.

---

## 9. Verify commands

```bash
make verify
make verify-http
./verify.sh          # JSON + CXB + cargo test + uxc_check
./verify.sh --http   # + live peer + python_forward
```

---

## 10. Related

- Glossary: [TERMINOLOGY.md](TERMINOLOGY.md)  
- Flows: [HOW_IT_WORKS.md](HOW_IT_WORKS.md)  
- FAQ: [FAQ.md](FAQ.md)  
- Secrets: [OPERATIONAL.md](OPERATIONAL.md)
