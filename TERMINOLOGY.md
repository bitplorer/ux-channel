<!-- pyramid -->
Read [START_HERE.md](START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Terminology — what each word means, does, and is not

**Purpose:** Stop ambiguous language. Every term below has a plain definition, what it **does**, what it is **not**, and where it lives in this package.

**Companion docs:** [HOW_IT_WORKS.md](HOW_IT_WORKS.md) (flows) · [REFERENCE.md](REFERENCE.md) (HTTP/API) · [FAQ.md](FAQ.md) · [STRUCTURE.md](STRUCTURE.md) · [OPERATIONAL.md](OPERATIONAL.md) · [SPEC/](SPEC/)

---

## How to read this glossary

| Column | Meaning |
|--------|---------|
| **Is** | One-sentence definition |
| **Does** | The job it performs at runtime |
| **Not** | Common mix-up — what people wrongly assume |
| **Where** | File / path in this repo (when applicable) |

Terms are grouped: **big picture → messages → security → wire → HTTP → software pieces → demo domain → process words**.

---

## 1. Big picture

### ux-channel

| | |
|--|--|
| **Is** | A **protocol + libraries** so different programs speak the same Intent → Result → ops contract. |
| **Does** | Defines message shapes, caps, JSON floor, optional CXB, and peer implementations. |
| **Not** | Not “only a Python web framework,” not a full multiplayer game server, not a database. |
| **Where** | This package root; full Python host also ships as `ux-channel-0.1.0` (zip, not required to understand the peer). |

### Wire-native

| | |
|--|--|
| **Is** | Design stance: the **wire messages** are the product boundary, not an internal optimization. |
| **Does** | Lets any language implement a peer that interops without embedding Python. |
| **Not** | Not “raw TCP only.” HTTP, in-process, and future WS can all carry the same IR. |

### Peer

| | |
|--|--|
| **Is** | Any process that can **accept an Intent** and **return a Result**. |
| **Does** | Validates IR, verifies caps when needed, runs an action, emits ops or an error. |
| **Not** | Not “only the HTTP server.” The in-process `Peer` struct is the **verify-only gate**; `uxc_peer` is one transport. Apply lives in cek-runtime / client JS. |
| **Where** | Gate: `rust/src/peer.rs`. HTTP: `bin/uxc_peer.rs`. |

### Client / surface

| | |
|--|--|
| **Is** | Whatever **sends Intents** and **applies ops** (browser UI, Python host, agent, another peer). |
| **Does** | Builds Intent, holds/mints caps, branches on `ok`, applies `ops[]` in order. |
| **Not** | Not trusted for authority — caps authorize, not “who connected.” |

### IR (Intermediate Representation)

| | |
|--|--|
| **Is** | The **shared message model**: Intent, Result, Op (and optional Trace). Version field `"v": "1"`. |
| **Does** | Gives every peer the same shapes so codecs and transports can vary without changing meaning. |
| **Not** | Not a binary format by itself. IR is **semantic**; JSON/CXB are **encodings of** the IR. |
| **Where** | Law: `SPEC/intent-result-ops.md`. Types: `types.rs`. |

### Permanent vs moving

| | |
|--|--|
| **Is** | Maintenance split: **permanent** = contract/law; **moving** = demos/transports you can replace. |
| **Does** | Prevents “the cart demo” from being mistaken for “the protocol.” |
| **Not** | Not “permanent code never changes” — permanent changes only via bugfix or IR major. |
| **Where** | [STRUCTURE.md](STRUCTURE.md). |

---

## 2. Messages (what goes on the wire, semantically)

### Intent

| | |
|--|--|
| **Is** | The **request document**: “please perform this action under this authority.” |
| **Does** | Carries `v`, `action`, optional `args`, optional `cap`, optional `request_id`, … |
| **Not** | Not a free-form REST path. Routing key is `action` (e.g. `Cart.add`), not URL alone. |
| **Where** | `types::Intent`, vectors under `conformance/vectors/intent/`. |

### Result (ResultDoc)

| | |
|--|--|
| **Is** | The **response document**: success flag + ordered effects and/or error. |
| **Does** | Always tells the client what happened in IR form (`ok`, `ops`, `error`, `meta`, optional `trace`). |
| **Not** | Not “HTTP status is the main API.” Status is secondary; **`ok` / `error.code` are primary.** |
| **Where** | `types::ResultDoc`. |

### Op (effect)

| | |
|--|--|
| **Is** | One **ordered side-effect** the client should apply (`{ "op": "toast", ... }`). |
| **Does** | Updates UI or client state: morph HTML, toast, set signal, navigate, … |
| **Not** | Not server-side DB writes by themselves (handlers may do side effects; **ops** are what the **client** is instructed to do). |
| **Where** | `types::Op` (flat JSON: `op` + fields). SPEC op table. |

### Action

| | |
|--|--|
| **Is** | Named operation string, usually dotted (`Cart.add`, `Counter.inc`). |
| **Does** | Selects which handler runs after the cap gate. |
| **Not** | Not the same as an HTTP route name (route is often fixed `/ux-channel/action`; body carries `action`). |

### Args

| | |
|--|--|
| **Is** | JSON object of inputs for the action (`sku`, `qty`, …). |
| **Does** | Fed to the handler; the **sealed subset** is hashed into the cap. |
| **Not** | Not fully trusted without a cap when the action requires one. |

### Sealed args

| | |
|--|--|
| **Is** | The arg object **bound into the capability** via `args_hash`. |
| **Does** | Prevents “mint for qty=1, then submit qty=999” without a new cap. |
| **Not** | Not “all possible form fields.” Only what the minting peer chose to seal. |

### Meta

| | |
|--|--|
| **Is** | Optional bag on Result (`action`, `runtime`, `peer`, `request_id`, …). |
| **Does** | Debugging and correlation; not the success branch. |
| **Not** | Not a substitute for `error.code`. |

### Trace / causal spine

| | |
|--|--|
| **Is** | Optional audit chain (`intent_id`, hops, signatures) for multi-peer causality. |
| **Does** | Answers “why did this op fire?” across peers (Phase 1.5 design). |
| **Not** | Not required for basic interop. JSON floor may omit it entirely. |
| **Where** | Vectors under `conformance/vectors/trace/`; design note `docs/archive/ux-channel-design-causal-surface.md`. |

### Error object / error codes

| | |
|--|--|
| **Is** | Structured failure on Result when `ok: false`: `code` + `message` (+ optional `fields`). |
| **Does** | Lets clients branch without parsing English. |
| **Not** | Not free-form only; codes in golden vectors are stable within a major. |

| Code | Means (this peer) |
|------|-------------------|
| `unauthorized` | Cap missing, invalid, expired, or mismatch |
| `validation` | Bad IR, bad JSON, wrong types (e.g. string `qty`) |
| `not_found` | Unknown action or unknown HTTP route |
| `internal` | Rare encode/server failure |
| `conflict` | Reserved vocabulary (SPEC); not the main demo path |

---

## 3. Security and authority


### Region (Python host) — **one slot**

| | |
|--|--|
| **Is** | **One** stable DOM slot (`data-channel-id`) the server can re-paint. |
| **Type** | Class `Region` (class style) **or** a function registered with `@ch.region`. |
| **Does** | `render(ctx) → HTML` for that single uid. |
| **Not** | **Not** renamed to RegionBook. **Not** a bridge, action, or whole page. |
| **Import** | `from ux_channel.host.api import Region` · `from ux_channel import Region` |
| **Where** | `ux_channel.host.region_component` (shim: `ux_channel.region_component`). |

**You almost always mean this word when you say “a region.”**

### RegionBook / RegionBook (Python host) — **the registry**

| | |
|--|--|
| **Is** | The **book of all regions** on a Channel: `uid → render` (`ch.regions`). |
| **Type** | Class `RegionBook` **≡** `RegionBook` (alias) — different type from `Region`. |
| **Preferred speech** | “region registry”; type name `RegionBook` or historical `RegionBook`. |
| **Does** | After an action, re-runs selected renders and builds **morph** ops. |
| **Not** | Not a single slot; not a rename of `Region`. |
| **Import** | Usually via `ch.regions` — you rarely construct it yourself. |
| **Where** | `ux_channel.host.regions` (shim: `ux_channel.regions`). |

```text
Region     = one chapter (one slot)
RegionBook = the whole book (registry on the channel)
```

### RegionDirectory (Python host) — **optional file discovery**

| | |
|--|--|
| **Is** | Opt-in loader that finds Region **classes** on disk/packages. |
| **Does** | Registers them into the RegionBook. |
| **Not** | Not required for core Intent plane; not RegionBook itself. |
### Bridge (Python host)

| | |
|--|--|
| **Is** | Mount/helpers for a **JS/npm island** (chart, map, editor). |
| **Does** | Placement attrs + bridge ops — client owns widget lifecycle. |
| **Not** | Not a Region (no server HTML morph of the island’s guts). |
| **Where** | `ux_channel.bridges`. Decision table: [`python/ONTOLOGY.md`](python/ONTOLOGY.md) §3. |

### Cap / capability token

| | |
|--|--|
| **Is** | A **server-minted, cryptographically signed string** carried on the Intent as `cap`. |
| **Does** | Proves the holder may run **this action** with **these sealed args** until expiry. |
| **Not** | Not a session cookie for the whole app. Not “mesh membership = trust.” Not the full args embedded (hash only). |
| **Where** | `cap.rs`, SPEC `capability.md`, oracle vector `conformance/vectors/cap/02-oracle-token.json`. |

### CapService

| | |
|--|--|
| **Is** | The mint/verify engine (itsdangerous-compatible in Cap 0.1). |
| **Does** | Issue + check tokens. **Rust:** `mint`/`verify`. **Python host:** `mint`/`verify`. |
| **Not** | Not HTTP itself; peer gate calls it before handlers. |

### Mint

| | |
|--|--|
| **Is** | **Create** a capability token (preferred product speech). |
| **Python** | `CapService.mint` / `ch.mint` / `registry.mint` |
| **Rust** | `CapService::mint`. |
| **Not** | Not verify. Prefer **mint** in new docs/code. |

### Verify (cap gate)

| | |
|--|--|
| **Is** | Checking a token before the action handler runs. |
| **Does** | Signature, expiry, action match, args hash, optional sub/scopes; SPEC also once/jti. |
| **Not** | Not optional when action is cap-required or when a cap field is present. |

### Present-cap-must-verify

| | |
|--|--|
| **Is** | Policy: **if Intent includes `cap` (even empty/bogus), verification always runs.** |
| **Does** | Stops open actions from ignoring a malicious/broken token. |
| **Not** | Not “open actions require a cap.” Open actions may omit `cap`; if present, still verify. |
| **Where** | `peer.rs`; health field `policy.present_cap_must_verify`. |

### Cap-required action

| | |
|--|--|
| **Is** | An action that **must** have a valid cap (this demo: `Cart.add`). |
| **Does** | Missing cap → `unauthorized` (“capability token required”). |
| **Where** | `CAP_REQUIRED` in `peer.rs`; health `cap_required`. |

### args_hash

| | |
|--|--|
| **Is** | `sha256(compact sorted JSON of sealed args)` truncated to **32 hex chars**. |
| **Does** | Binds the token to exact arg bytes (canonical JSON subset). |
| **Not** | Not full SHA-256 hex (only first 32 hex characters — frozen by oracle). |

### Oracle secret

| | |
|--|--|
| **Is** | Public conformance secret: `conformance-oracle-secret-32chars!!` (constant `ORACLE_SECRET`). |
| **Does** | Lets tests and golden vectors mint/verify the same tokens across languages. |
| **Not** | **Never production.** Anyone with the repo can mint for it. |

### UXC_CAP_SECRET

| | |
|--|--|
| **Is** | Env var: private signing/verification secret for `uxc_peer`. |
| **Does** | Production authority root for mint/verify. |
| **Not** | Not optional in production. Empty/unset without allow → peer **refuses to start**. |

### UXC_ALLOW_ORACLE_SECRET

| | |
|--|--|
| **Is** | Env flag (`1` / `true`) that **explicitly** allows the public oracle secret for local demo/CI. |
| **Does** | Opt-in to demo mode; health shows `demo_mode: true` and stderr WARNINGs. |
| **Not** | Not a production setting. |

### once / jti

| | |
|--|--|
| **Is** | SPEC single-use cap: `once=true` requires unique `jti`; replay must fail. |
| **Does** | (When implemented) prevents double-submit of destructive controls. |
| **Not** | Health: `once_jti_enforced: true`. Replay and store-down refuse. |

### Attenuation

| | |
|--|--|
| **Is** | Narrowing a cap before forwarding (fewer scopes, tighter action, shorter life). |
| **Does** | Least privilege across peer hops (design; core requirement remains verify action+args_hash+expiry). |
| **Not** | Not fully productized as a separate mint API in this package’s demo peer. |

---

## 4. Wire and codecs

### Wire / wire format

| | |
|--|--|
| **Is** | How IR documents become **bytes** on the network or disk. |
| **Does** | Encode Intent/Result for transport; decode on the other side. |
| **Not** | Not a second business API — same Intent/Result meaning. |

### JSON floor

| | |
|--|--|
| **Is** | Rule: **JSON always works** for interop (`application/ux-channel+json`). |
| **Does** | Guarantees browsers and application clients need no binary codec. |
| **Not** | Not “JSON is the only codec forever.” Binary is opt-in **above** the floor. |
| **Where** | `wire_json.rs`; media type constant in docs. |

### Media type

| | |
|--|--|
| **Is** | HTTP Content-Type / Accept label for a codec. |
| **Does** | Tells peers how to parse request/response bodies. |

| Media type | Codec name |
|------------|------------|
| `application/ux-channel+json` | `json` (floor) |
| `application/ux-channel+cxb` | `cxb` (optional dense binary) |

### CXB (Channel eXchange Binary)

| | |
|--|--|
| **Is** | Domain binary encoding of Intent/Result/ops documents (CXB1 plain / CXBZ compressed). |
| **Does** | Dense tags, interned strings, CRC; smaller/faster when both sides support it. |
| **Not** | Not a different protocol. Not required. Not yet negotiated on Rust HTTP `/action`. |
| **Where** | Library: `cxb.rs`, `op_tags.rs`. Frozen: `conformance/expected/cxb/`. Spec in package `docs/core/CXB.md` (zip). |

### CXB1 / CXBZ

| | |
|--|--|
| **Is** | Frame magics: `CXB1` = uncompressed frame; `CXBZ` = zlib-compressed payload frame. |
| **Does** | Sniffable first 4 bytes (`is_cxb`). |
| **Not** | Not two different IR versions — same document kinds inside. |

### Codec vs format (health honesty)

| Term | Means in health JSON |
|------|----------------------|
| **`codecs`** | What the **library** can encode/decode (e.g. `json`, `cxb`). |
| **`formats`** | What this **HTTP surface actually serves today**. |
| **`accept_response`** | What you may put in `Accept` **today** and get back. |

**Rule:** Never list `+cxb` under `formats` until Accept negotiation really works. Today: JSON only on HTTP; CXB library-ready.

### Codec negotiation

| | |
|--|--|
| **Is** | Choosing encode/decode from HTTP `Content-Type` (request) and `Accept` (response). |
| **Does** | (Designed) Request CT → decode; Accept → encode; else JSON floor; optional fallback header. |
| **Not** | **Not implemented on Rust `uxc_peer` yet.** Python package has `wire/negotiate.py`. |
| **Where** | Design: HOW_IT_WORKS §8; package WIRE.md. |

### Freeform / W_FREE

| | |
|--|--|
| **Is** | CXB wire type for open-ended maps (often MessagePack inside). |
| **Does** | Encodes arbitrary JSON objects that are not dense-tagged. |
| **Not** | Not guaranteed byte-identical across languages (key order); **decode interop** is the bar. |

### Op tags / dense tags

| | |
|--|--|
| **Is** | Small integers for common op field names in CXB (tags **1–63** reserved core). |
| **Does** | Shrink binary ops; **append-only** (never reuse a number for a new meaning). |
| **Where** | `op_tags.rs`; breaking policy. |

---

## 5. HTTP surface terms

### `/ux-channel/action`

| | |
|--|--|
| **Is** | Main product endpoint: **POST Intent → Result**. |
| **Does** | Full gate + dispatch; returns Result-shaped body. |
| **Not** | Not REST-per-action URLs; action is inside the Intent. |

### `/ux-channel/health`

| | |
|--|--|
| **Is** | Capability advertisement (actions, formats, codecs, policy flags, demo_mode). |
| **Does** | Lets clients discover what is real **today** without guessing. |
| **Not** | Not a substitute for conformance vectors. |

### Mint (Channel / cek-runtime Host)

| | |
|--|--|
| **Is** | Product mint on Channel `CekHostCapService` (cek-runtime Host). |
| **Does** | Issues Caps the Host verifies. Classic `CapService` remains for floor tests. |
| **Not** | Not a Peer HTTP endpoint. `Peer` is verify-only (ADR 0011). |

### HTTP status (secondary)

| Status | When (this peer) |
|--------|------------------|
| `200` | `Result.ok == true` |
| `401` | `error.code == unauthorized` |
| `400` | Other Result errors |
| `500` | Encode catastrophe |
| `404` | Unknown route |

Clients still branch on **Result**, not status alone.

### demo_mode

| | |
|--|--|
| **Is** | Health flag: peer is using public/allow-listed oracle-capable secret. |
| **Does** | Warns operators “this is not production authority.” |
| **Not** | Not a separate code path for cart logic — same IR; different secret policy. |

### Result-shaped errors

| | |
|--|--|
| **Is** | Even wire/parse failures on the action path return a **Result** body (`ok: false`), not bare HTML. |
| **Does** | Clients always parse one document type. |
| **Where** | `Peer::handle_json` / `wire_fail`. |

---

## 6. Software pieces (names in the tree)

| Name | Is | Does | Not |
|------|----|------|-----|
| **`types`** | IR structs | Serde models for Intent/Result/Op | Not HTTP |
| **`wire_json`** | JSON codec | encode/decode floor | Not CXB |
| **`cap`** | Cap crypto | mint/verify | Not action handlers |
| **`cxb`** | Binary codec | encode/decode CXB1/CXBZ | Not HTTP negotiation yet |
| **`op_tags`** | Dense key table | Tag ↔ field name | Not op runtime |
| **`peer`** | Classic demo gate | validate → cap verify → dispatch | Not a mint authority |
| **`actions`** | Demo handlers | Cart / Counter | Not the product forever (moving) |
| **`uxc_peer`** | HTTP binary | Serves action/health/mint/demo page | Not the only possible transport |
| **`uxc_check`** | Conformance runner | Loads vectors, oracle, CXB, optional `--http` | Not a production server |
| **`python_forward`** | Tiny adapter | Mint + POST Intent; return ops unchanged | Not a full ASGI host |
| **`python/ux_channel`** | Full Python host package | Wire, caps, ASGI, CXB oracle, bridges | Not under `peers/` |
| **`verify.sh`** | Local CI script | One-command green harness | Not shipped as product API |
| **`startup-peer.sh`** | Dev helper | Idempotent demo peer on :8787 | Uses oracle allow by default |
| **conformance vectors** | Golden JSON/CXB | Executable interop law | Not optional examples only |
| **SPEC** | Normative drafts | What peers must honor | Not the Rust demo cart |

---

## 7. Demo domain (moving — illustrative only)

| Name | Is | Does |
|------|----|------|
| **`Cart.add`** | Cap-required demo action | Adds a cart line: toast + morph + signal_set last sku |
| **`Counter.inc` / `Counter.get`** | Open demo actions | Bump/read an atomic counter via signal_set |
| **`sku` / `qty` / `by`** | Demo args | `qty`/`by` must be JSON integers (no string coercion) |
| **morph HTML escape** | Safety pattern | Free-form strings in HTML/toast are escaped |
| **signal raw value** | Data pattern | `signal_set` keeps semantic raw values (not HTML) |

These prove the IR works. **Replace them** without an IR major as long as permanent tests stay green.

---

## 8. Ops vocabulary (client effects)

| `op` | What it does for the client |
|------|-----------------------------|
| **`toast`** | Show a short human message (`message`, optional `level`) |
| **`morph`** | Patch DOM at `target` with `html` |
| **`signal_set`** | Set client store key `name` to `value` |
| **`navigate`** | Hard navigation to `href` |
| **`noop`** | Explicit no-op (optional reason) |
| **`swap` / `remove` / `set_text` / …** | Other DOM/effects (SPEC); not all used by demo |

**Apply order:** ops run **in array order**. Unknown ops: ignore safely or refuse — never silent half-application of security-sensitive effects.

---

## 9. Process and quality words

| Term | Is | Does |
|------|----|------|
| **Green** | Checks pass | Safe to claim that layer works |
| **Gap** | Known incomplete vs SPEC | Documented; do not market as done |
| **Kill criteria** | Must-never-happen bugs | Listed in `SPEC/INVARIANTS.md` |
| **Conformance** | Cross-language agreement | Vectors + harness + `uxc_check` |
| **Oracle (cap/CXB)** | Reference implementation / public test secret / frozen blobs | Interop ground truth for tests |
| **Structural re-encode** | Decode then encode without requiring identical bytes | Proves semantic round-trip when freeform order differs |
| **Fail closed** | Prefer refuse over insecure default | e.g. peer won’t start with silent oracle secret |
| **Append-only tags** | CXB/op tag numbers never reused | Prevents silent decode of wrong field |
| **Breaking change** | Needs IR major | See `BREAKING_CHANGE_POLICY.md` |

---

## 10. Environment variables (operator vocabulary)

| Variable | Is | Does |
|----------|----|------|
| **`UXC_CAP_SECRET`** | Private secret | Signs/verifies caps (≥ 16 chars production) |
| **`UXC_ALLOW_ORACLE_SECRET`** | Demo allow flag | Permits public oracle secret |
| **`UXC_HOST`** | Bind host | Default `0.0.0.0` |
| **`UXC_PORT`** | Bind port | Default `8787` |

---

## 11. Confusable pairs (quick disambiguation)

| Don’t confuse… | With… | Difference |
|----------------|-------|------------|
| **IR** | **CXB** | IR = meaning; CXB = one binary encoding of that meaning |
| **Action** | **Op** | Action = server handler name; Op = client effect |
| **Cap mint** | **Action run** | Mint issues permission; action uses it |
| **`formats`** | **`codecs`** | HTTP serves today vs library can do |
| **`ok: false`** | **HTTP 500** | Most failures are still Result + 4xx; 500 is encode catastrophe |
| **Oracle secret** | **Production secret** | Public test vs private authority |
| **Peer gate** | **HTTP server** | Gate is permanent logic; HTTP is one moving transport |
| **signal_set value** | **morph html** | Raw data vs escaped markup |
| **once/jti SPEC** | **once/jti Rust** | Required by law; enforced via `mint_once` + `MemoryNonceStore` |
| **Permanent** | **Moving** | Law/vectors/types vs demos/actions/HTTP chrome |

---

## 12. One-line cheat sheet

```text
Client --Intent(action,args,cap)--> Peer gate --verify cap--> Action --> Result(ok,ops|error) --> Client applies ops
                │                         │
                │                         └── authority is the Cap, not the TCP socket
                └── bytes today: JSON floor; CXB = same IR, denser bytes (library ready; HTTP negotiate later)
```

---

## 13. Where to go next

| Need | Doc |
|------|-----|
| Flows and order of steps | [HOW_IT_WORKS.md](HOW_IT_WORKS.md) |
| HTTP / curl / modules | [REFERENCE.md](REFERENCE.md) |
| Short Q&A | [FAQ.md](FAQ.md) |
| Field tables (normative) | [SPEC/intent-result-ops.md](SPEC/intent-result-ops.md), [SPEC/capability.md](SPEC/capability.md) |
| Must-hold laws | [SPEC/INVARIANTS.md](SPEC/INVARIANTS.md) |
| Secrets / health honesty | [OPERATIONAL.md](OPERATIONAL.md) |
| Law vs demo | [STRUCTURE.md](STRUCTURE.md) |
| Run checks | `./verify.sh` · [README.md](README.md) |
