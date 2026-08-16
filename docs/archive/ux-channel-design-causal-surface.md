# Design Note — Causal Spine, Surface Negotiation & Differential Ops

**Status:** Proposed long-term extension (IR-additive, optional)  
**Target:** Phase 1.5 (spec) → Phase 3 (transports + handshake) → Phase 7 (hardening)  
**Principle:** Never break the JSON floor or day-1 DX. All new fields are optional. Caps and core Intent/Result remain the only required contract.

---

## 1. Why this layer exists

The base model (Intent → Result.ops) is already powerful.  
The next decade of value comes from three missing properties:

1. **Causality & audit that travel** — “Why did this op fire?” must be answerable across peers, languages, and time.
2. **Surface polymorphism** — Different peers understand different op dialects. Negotiation prevents silent degradation.
3. **Efficiency under continuous update** — Full morphs are fine for rare actions; high-frequency UIs, dashboards, and multi-device sync need deltas.

These three turn a good coordination library into durable infrastructure.

---

## 2. Causal Spine (optional Result envelope)

```text
Result {
  ok: bool
  ops: Op[]
  error?: ...
  // NEW — optional
  trace?: {
    intent_id: string          // stable ID of originating Intent
    hops: Hop[]                // ordered, signed
    caused_by?: string         // parent intent_id (pipelines / fan-out)
  }
}

Hop {
  peer: string                 // peer identity / node id
  at: timestamp                // when this peer handled it
  cap_fingerprint: string      // attenuated cap that authorized this hop
  signature: bytes             // peer signs (intent_id + previous hop hash)
}
```

**Rules**
- Presence of `trace` is negotiated or requested via Accept / Intent flag.
- Caps may carry `max_hops` and `require_trace`.
- Replay tools can reconstruct the exact causal graph without reading application logs.
- JSON floor: omit `trace` entirely when not needed. CXB gets dense tags later.

**Security**
- Host always verifies the originating cap *before* any guest or forward.
- Hop signatures are append-only; a later peer cannot rewrite earlier hops.

---

## 3. Surface Capability Negotiation

At peer handshake (HTTP, UDS, WS, stdio):

```text
PeerHello {
  ir_version: "0.1"
  formats: ["json", "cxb"]
  surfaces: [                    // what ops this peer can apply
    "dom.morph",
    "dom.toast",
    "bridge.mount",
    "hardware.move",
    "delta.patch",               // advertises differential support
    "voice.speak",
    ...
  ]
  actions: [...]                 // optional: actions this peer serves
}
```

**Routing & emission rules**
- A peer that cannot interpret an op must either:
  - drop it with a clear warning in Result, or
  - forward to a peer that can (mesh), or
  - refuse the Intent with a typed error.
- Prefer emitting the richest dialect the *receiving surface* understands.
- Default (no negotiation) = classic DOM ops only → zero breakage for existing clients.

---

## 4. Differential / Incremental Ops

New optional op families (free-string types first, dense tags later):

| Op type        | Purpose                              | When to emit                  |
|----------------|--------------------------------------|-------------------------------|
| `delta.patch`  | JSON-patch or RFC 6902 style         | High-frequency region updates |
| `delta.crdt`   | Compact CRDT op                      | Multi-writer collaborative    |
| `delta.signal` | Incremental signal / store update    | Live metrics, counters        |
| `delta.remove` | Tombstone / observed-remove          | Cleanup                       |

**Emission policy**
- Only when the target surface advertised support.
- Full `morph` remains the universal fallback.
- Server may keep a short “last known state” hash per region to decide full vs delta.

This keeps the mental model simple: ops are still data; the surface decides how rich it can be.

---

## 5. Deterministic Replay & Session Recorder

Because every Intent and Result is pure data + caps:

- Record a stream of `(Intent, Result, timestamps, peer)`.
- Replay against any peer version that implements the same IR major.
- Use cases: certification, regression, agent behaviour review, compliance export.

**Minimal implementation**
- `uxchannel record` / `uxchannel replay` CLI (Phase 3).
- Golden session files live next to the existing conformance vectors.
- No change to runtime hot path.

---

## 6. Metering Envelope (optional Receipt)

For marketplace / multi-tenant later:

```text
Receipt {
  intent_id
  principal
  action
  cost: { units, currency? }
  peer
  at
}
```

Emitted alongside or inside Result when the action is metered.  
Keeps billing orthogonal to the effect system.

---

## 7. Integration order (recommended)

| When          | Work |
|---------------|------|
| **Phase 1.5** | Spec the optional fields + golden vectors for `trace` and surface hello |
| **Phase 3**   | Handshake carries surfaces; WS progressive Results can carry partial traces |
| **Phase 7**   | Replay harness, hop signature verification tests, delta emission policy |
| **Later**     | Dense CXB tags, CRDT helpers, metering settlement |

---

## 8. Non-goals for this note

- Making trace mandatory
- Replacing morph with deltas
- Full CRDT library inside the core
- Changing the required Intent/Result shape
- Any breaking change to existing Python or browser clients

---

## 9. Decision rule

After the first real Rust peer is running (end of Phase 2):

> Does the causal spine + surface negotiation make the second peer *dramatically* more useful for audit, multi-surface, or agent scenarios?

- Yes → accelerate Phase 1.5 material into the main line.
- No → keep as documented optional extensions.

This preserves optionality while locking the design early enough that peers do not diverge.

---

**Bottom line**

We scale the *contract*, not the languages.  
Causal spine, surface negotiation and differential ops are the smallest additions that give the contract decade-scale leverage.
