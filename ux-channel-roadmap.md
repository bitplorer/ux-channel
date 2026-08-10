# Complete Roadmap — UX-Channel as a Wire-Native Peer Platform

**Scope:** Take what you have (Intent / Result / ops, CXB, caps, bridges, Python ASGI, Rust codec) and grow it into a **stable protocol + multi-runtime mesh**, without losing the day-1 DX (JSON, `encode`/`decode`, no plugin anxiety).

---

## North Star

```text
Any peer  ── Intent { action, args, cap } ──▶  Any peer
Any peer  ◀── Result { ok, ops[], error } ──  Any peer

Surfaces apply ops: DOM | bridge | WASM | engine | hardware
```

**Success:** a non-Python peer (Rust binary or WASM) handles a real action end-to-end; browser still works; caps still hold.

---

## Principles (non-negotiable on every phase)

| # | Rule |
|---|------|
| 1 | **One IR** — Intent / Result / ops; no parallel RPC style |
| 2 | **JSON floor** — browsers & day-1 always work |
| 3 | **CXB upgrade** — density/binary when opted in |
| 4 | **Caps travel** — authority on the Intent, not “trust the socket” |
| 5 | **Peers > FFI** — process/wire first; in-process native is optional speed |
| 6 | **Soft safety** — never brick; complete recovery / ceilings / CRC |
| 7 | **App API stays boring** — `encode` / `decode` / `configure_wire` / actions |
| 8 | **Optional power, never required complexity** — causal spine, surface negotiation, deltas, metering are additive envelopes only |

---

## Horizon Map

```text
NOW (0.1)     →  FOUNDATION     →  PEERS        →  SURFACES     →  PLATFORM
sandbox lib       freeze wire       Rust/WASM       WASM islands    mesh, marketplace
                  Python host       sidecars        edge workers    multi-impl
```

---

## Phase 0 — Freeze what you have (1–2 weeks)

**Goal:** 0.1 is a reliable product, not a moving pile of experiments.

| Track | Work |
|-------|------|
| **Spec** | Write `SPEC/intent-result-ops.md` + `SPEC/cxb.md` + `SPEC/capability.md` as **normative** (versioned, field tags, media types) |
| **Python** | Public API freeze list: wire, actions, ops builders, ASGI mount, config/env (`UX_CHANNEL_*` only) |
| **CXB** | Python oracle + Rust `_cxb_native` (CXB1/CXBZ) + tests as **conformance suite** |
| **Cleanup** | No legacy UID_*, no public plugin surface for apps, docs match reality |
| **Quality** | Full battery green; realworld bench; chaos/pen on channel+DOM as you already run |

**Exit criteria**

- [x] Spec drafts started (`SPEC/intent-result-ops.md`, `SPEC/capability.md`, public API freeze list)
- [ ] Spec docs checked in and versioned `ir/0.1`, `cxb/1` (CXB.md already treated as normative inside package)
- [ ] Conformance tests: any encoder that passes can interop with Python decode
- [ ] `encode(doc, format="cxb")` auto-native; no app plugin registration
- [ ] Ship/tag **ux-channel 0.1** / **ux-dom 0.1** cleanly

---

## Phase 1 — Wire & trust as a portable contract (2–4 weeks)

**Goal:** the wire is implementable by a stranger without reading Python source.

| Deliverable | Detail |
|-------------|--------|
| **IR 0.1 freeze** | Intent/Result field sets, op dense tags 1–63, free-key/freeform rules |
| **CXB 1.0 “stable”** | Magic, CRC, CXBZ gates, intern budgets, kind 1/2/3 |
| **Cap 0.1** | Canonical bytes to sign, attenuation, expiry, action bind — **language-agnostic test vectors** |
| **Media types** | `application/ux-channel+json` / `+cxb` (+ msgpack optional) |
| **Conformance pack** | Golden files: Intent/Result samples × JSON × CXB × bad CRC × CXBZ |
| **Transport notes** | HTTP POST action, Accept negotiation, WS framing sketch (not full mesh yet) |

**Exit criteria**

- [x] Test vectors in CI (Python structural harness)
- [x] Cap vectors verified by a **second implementation** (Rust `cap` + `uxc_check`)
- [x] Breaking-change policy written (tag numbers never reused)
- [x] CXB expected blobs frozen under `conformance/expected/cxb/` (14 blobs from pure-Python oracle)

---

## Phase 1.5 — Causal spine, surface negotiation & differential ops (spec only) (1–2 weeks)

**Goal:** Lock the highest-leverage optional extensions early so every future peer implements the same envelopes.  
See full design: `ux-channel-design-causal-surface.md`

| Deliverable | Detail |
|-------------|--------|
| **Causal spine** | Optional `Result.trace` with signed hops + `intent_id` + `caused_by` |
| **Surface hello** | Peer handshake advertises supported op dialects (`dom.morph`, `delta.patch`, `hardware.move`, …) |
| **Differential ops** | Optional op families `delta.patch`, `delta.crdt`, `delta.signal` (full morph remains universal fallback) |
| **Replay vectors** | Session recording format + golden replay files for deterministic re-execution |
| **Metering envelope** | Optional `Receipt` object (principal + action + cost) for later marketplace |

**Rules**
- All fields optional. JSON floor and existing clients break zero.
- Caps may declare `max_hops` and `require_trace`.
- Spec + golden vectors only in this phase; runtime lands in Phase 3 / 7.

**Exit criteria**

- [x] Design note accepted and referenced from main SPEC
- [x] Golden vectors for trace + surface hello exist
- [x] Explicit non-goal: none of these become required for basic Intent/Result interop

---

## Phase 2 — Rust peer crate (core of “wire-native”) (4–6 weeks)

**Goal:** Rust is a **peer**, not only a `.so` inside Python.

```text
ux_channel_rs/
  types     Intent, Result, Op
  cxb       encode/decode (share logic with cxb_rs)   ← done (peer crate)
  cap       sign/verify                               ← done
  registry  action handlers                           ← Cart.add / Counter.inc
  transport http + unix framed                        ← HTTP done; UDS later
```

| Milestone | Outcome |
|-----------|---------|
| **2a** | Types + JSON roundtrip vs golden files — **done** (`uxc_check`) |
| **2b** | Cap verify compatible with Python issuer — **done** (oracle + itsdangerous interop) |
| **2c** | `uxc_peer` binary: HTTP, `Cart.add` → toast+morph Result — **done** |
| **2d** | Python **forward** adapter: selected actions → Rust sidecar, Result back unchanged — **done** |
| **2e** | CXB encode/decode in peer crate; decode frozen oracle blobs — **done** |

**Exit criteria**

- [x] Pure Rust HTTP peer alone can serve `Cart.add` (Python optional)
- [x] Python host can forward one hot action and return ops unchanged
- [x] Rust CXB codec decodes frozen expected blobs; structural re-encode round-trips
- [ ] Browser → Python ASGI → Rust worker → Result.ops → browser (wire into full package ASGI when integrating)
- [ ] Bench: sidecar latency budget documented (p95)
- [ ] HTTP Accept `application/ux-channel+cxb` response path (optional)

---

## Phase 3 — Transports, handshake & progressive Results (3–4 weeks)

**Goal:** boring, production transports + the first runtime of Phase 1.5 envelopes.

| Transport | Use |
|-----------|-----|
| **HTTP/1.1+** | Public & sidecar (same paths as today) — **peer MVP exists** |
| **Unix socket** | Local high-trust workers (length-prefix + CXB) |
| **WebSocket** | Streaming multi-Result / progressive ops + partial traces |
| **stdio** (optional) | CLI agents / subprocess peers |

| DX / Envelope | Work |
|---------------|------|
| **CLI** | `uxchannel peer check`, `uxchannel cap mint`, `uxchannel cxb inspect`, `uxchannel record` / `replay` |
| **Health + Hello** | `/ux-channel/health` + peer handshake (IR version, formats, **surfaces**) — health MVP exists |
| **Observability** | OTEL hooks: intent_id, action, peer, cap principal, op count, hop depth |
| **Progressive** | Multi-Result streams can carry partial `trace` and delta ops when negotiated |

**Exit criteria**

- [ ] Handshake rejects mismatched IR major version
- [ ] Surface capability advertisement works (at least `dom.*` + one experimental `delta.*`)
- [ ] WS progressive ops demo (long job → toast / delta updates)
- [ ] Basic session record/replay round-trip against golden vectors
- [ ] Runbook: deploy Python+Rust sidecar

---

## Phase 4 — Surfaces: bridges + WASM islands (4–6 weeks)

**Goal:** ops reach more than “server HTML morph.”

| Track | Work |
|-------|------|
| **4a Bridge WASM** | `BridgeManifest.runtime = "wasm"`, SRI/integrity, thin JS adapter |
| **4b Guest firewall** | Reuse sealed protocol + GuestRuntime ceilings for WASM |
| **4c Sample islands** | `wasm:hello`, canvas/vision or chart sample |
| **4d Optional cxb.wasm** | Browser CXB when `Accept: +cxb` / large payloads |

**Exit criteria**

- [ ] `bridge.mount` loads WASM with sealed methods only
- [ ] Malicious export / oversize payload blocked
- [ ] No change to app-facing action API

---

## Phase 5 — Server WASM actions (sandboxed plugins) (4–6 weeks)

**Goal:** untrusted or polyglot handlers as **bytes-in / bytes-out** guests.

```text
Intent (CXB) → Wasmtime → Result (CXB)
imports: limited (clock, log, optional allowlisted HTTP)
```

| Work | Detail |
|------|--------|
| Guest ABI 0.1 | `handle_intent(ptr,len) -> (ptr,len)` + alloc |
| Host runner | Python and/or Rust registry entry `kind=wasm` |
| Policy | Fuel/time limits, memory max, no host secrets in linear memory |
| Packaging | `.wasm` + manifest (actions, max_mem, imports) |

**Exit criteria**

- [ ] Third-party sample action as WASM, capped, audited
- [ ] Cap still verified **on host** before guest runs
- [ ] Escape tests: guest cannot call arbitrary host actions

---

## Phase 6 — Mesh membership (optional but strategic) (6–10 weeks)

**Goal:** scopes, discovery, multi-peer routing — still single-player product sense (no “MMO server” claim).

| Piece | Detail |
|-------|--------|
| **Scope** | `shop.floor.1` peers join with scoped caps |
| **Advertise** | Peer publishes actions it serves |
| **Route** | Intent → peer that owns action (local first) |
| **Patterns** | fan-out, forward, gather (Results/ops merge policy) |
| **Transports** | existing HTTP/UDS/WS; later WebRTC datachannel if needed |

**Exit criteria**

- [ ] 3 peers in one scope (e.g. Python UI, Rust worker, WASM edge stub)
- [ ] Audit log: intent path across peers
- [ ] Failure: peer down → clear Result.error, no silent drop

---

## Phase 7 — Platform hardening (ongoing, parallel after P2)

| Area | Work |
|------|------|
| **Conformance CI** | Matrix: Python × Rust × (WASM codec) × JSON/CXB |
| **Security** | Cap pen tests, CXB fuzz, bridge/WASM abuse, rate limits |
| **Perf** | p95 Intent path; CXB native; sidecar hop budget |
| **Versioning** | IR minor additive; CXB tags append-only |
| **Docs** | Protocol book + “write a peer in 30 minutes” |
| **ux-dom** | data-channel-* only; multi-region; live DOM regression pack |

---

## Phase 8 — Ecosystem (only after P2–P4 real)

| Bet | When it makes sense |
|-----|---------------------|
| Public peer SDK (Rust first, then others) | After 2 independent peers in prod |
| Plugin marketplace (WASM actions) | After P5 + signing |
| Formal standard / open repo “channel-ir” | After external consumer #1 |

Don’t start P8 early — empty platforms die.

---

## Dependency Graph (order that fits)

```text
P0 Freeze 0.1
 └─► P1 Spec + vectors + cap portability
      └─► P1.5 Causal / surface / delta envelopes (spec + vectors)
           └─► P2 Rust peer + Python forward + CXB codec   ← **current milestone**
                ├─► P3 Transports + handshake + progressive + replay
                ├─► P4 WASM bridges (client)
                └─► P5 WASM actions (server)
                     └─► P6 Mesh
                          └─► P8 Ecosystem
P7 Hardening ──────────────────────────── (parallel from P1 onward)
```

---

## One-Page “Current Next Steps”

**Done (this execution)**

- SPEC + freeze + breaking-change policy
- Conformance pack with structural harness (Python) — green
- Oracle cap token + Rust **cap verify / mint** (itsdangerous-compatible)
- Rust peer HTTP: `POST /ux-channel/action` for `Cart.add` / `Counter.inc`
- `uxc_check` proves vectors + oracle + CXB expected + optional live HTTP
- Python forward example returns `Result.ops` unchanged
- **CXB expected blobs** frozen from pure-Python oracle (14 files)
- **Rust CXB** encode/decode in `peers/ux_channel_rs` (decode oracle blobs green)

**Immediate remaining order**

1. **P2 polish** — HTTP Accept `+cxb` response path; p95 sidecar note; wire Python ASGI forward into full 0.1.0 package
2. **Byte-identity** — align Rust msgpack freeform key order with Python oracle for encode sha256 match (decode already green)
3. **P3** — surface hello runtime + UDS framed transport
4. Only then WASM (P4) or mesh (P6)

---

## Bottom Line

| Roadmap layer | What “big” means |
|---------------|------------------|
| **P0–P1** | Reliable product + portable contract |
| **P1.5** | Causal + surface + delta envelopes locked early (decade leverage) |
| **P2–P3** | Wire-native peers are **real** (this is the strategic jump) |
| **P4–P6** | Surfaces + plugins + mesh without breaking the IR |
| **P7–P8** | Hardening + ecosystem only after peers earn it |
