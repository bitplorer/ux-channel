# Permanent vs moving — clarity for long-term maintenance

**Purpose:** Stop mixing *law* with *example*.  
Long-term stability comes from a small permanent core; confusion comes from treating demos and transports as the product.

Layout decision: [`ARCHITECTURE.md`](ARCHITECTURE.md).  
Python host permanence: [`python/STRUCTURE.md`](python/STRUCTURE.md) · map: [`python/ONTOLOGY.md`](python/ONTOLOGY.md).  
Glossary: [`TERMINOLOGY.md`](TERMINOLOGY.md). Reference: [`REFERENCE.md`](REFERENCE.md).  
Full narrative (flows, algorithms, CXB negotiation status): [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md).

```text
┌─────────────────────────────────────────────────────────────┐
│  PERMANENT (contract) — change only via major IR version    │
│  SPEC/ · conformance vectors · types · wire_json · cap API  │
│  present-cap policy · Result shape · error codes in vectors │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ implements / verifies
┌─────────────────────────────────────────────────────────────┐
│  MOVING (peer surface) — replace freely without IR change   │
│  demo actions · HTTP server · forward adapters · demo HTML  │
│  CXB encode technique details · CI glue · generative tests  │
└─────────────────────────────────────────────────────────────┘
```

---

## Permanent

| Asset | Why permanent |
|-------|----------------|
| `SPEC/intent-result-ops.md` | IR shape |
| `SPEC/capability.md` | Cap semantics |
| `SPEC/INVARIANTS.md` | Testable laws |
| `SPEC/BREAKING_CHANGE_POLICY.md` | When a major is required |
| `PUBLIC_API_FREEZE.md` | Application public names (host package) |
| `conformance/manifest.json` + `vectors/**` | Executable interop law |
| `conformance/expected/cxb/**` | Frozen CXB blobs (append-only tags) |
| Peer: `types`, `wire_json` | IR encode/decode floor |
| Peer: `cap` API + verify rules | Authority path (oracle constant = test-only) |
| Peer: `peer` gate (IR + present-cap) | Shared entry for “run action” |
| `python/src/ux_channel/` (host package) | Reference Python implementation (wire, cap, ASGI) |
| `rust/` (`ux_channel_rs` crate) | Second peer implementation (types, cap, CXB, HTTP) |

**Rule:** A change here is either a **bugfix** (behavior already required by SPEC/vectors) or a **new major**.

---

## Moving

| Asset | Why moving |
|-------|------------|
| `actions` (`Cart.add`, `Counter.*`) | Illustrative handlers, not the product |
| Escape of morph/toast in demos | Safety pattern for DOM surfaces; keep when domain HTML is produced |
| `bin/uxc_peer` | One HTTP transport; others may replace it |
| `demo.html` inside the peer binary | Smoke UI |
| `demos/python_forward` | Adapter example |
| `cxb` encode freeform key order | Codec technique until byte-identical freeze |
| Roadmap / design notes at repo root | Planning, not law |

**Rule:** Replace or delete moving pieces without an IR major **as long as** permanent tests still pass.

---

## Dependency DAG (minimal coupling)

```text
types  →  wire_json | cap | op_tags
              ↓
            peer::handle_*   (only permanent entry for “run Intent”)
              ↓
             actions (domain / demo)
              ↓
            bins (HTTP, check)
```

| Rule | Why |
|------|-----|
| Domain never reimplements cap verify | Cap rules stay in `cap` + `peer` gate |
| Transport never invents Result shape by hand | Use `peer.handle_json` / encode helpers |
| Demo has no IR version checks | Gate owns that |
| Replace `actions` without touching `cap` | Future-ready domains |

**Debug path:** shaped error → read `error.code` → unauthorized/validation from gate → look at `peer`/`cap`; domain-specific → look at `actions`.

| Code | Where to look |
|------|----------------|
| `unauthorized` | `peer` gate + `cap` |
| `validation` | IR validate, wire parse, or domain field rules in `actions` |
| `not_found` | unknown action (`actions`) or unknown HTTP route (`uxc_peer`) |
| `internal` | encode path or cap construction |

---

## Secrets

`ORACLE_SECRET` is **conformance-only**, never production. Production secrets are injected by the host peer (`UXC_CAP_SECRET`). See [`OPERATIONAL.md`](OPERATIONAL.md).
