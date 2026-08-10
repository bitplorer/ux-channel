# FAQ — short answers

Words: [TERMINOLOGY.md](TERMINOLOGY.md) · Flows: [HOW_IT_WORKS.md](HOW_IT_WORKS.md) · API: [REFERENCE.md](REFERENCE.md)

---

### Why do some things have two names (`mint`/`sign`, `RegionBook`/`RegionBook`)?

**One intent, one function — two spellings only when history or Rust parity requires it.**

| Intent | Prefer | Same as |
|--------|--------|--------|
| Create cap | `mint` | `sign` |
| Slot registry type | `RegionBook` | `RegionBook` |
| One slot | `Region` only | — |

Full table: [`NAMING.md`](NAMING.md).

### Did Region get renamed to RegionBook?

**No.** They were never the same thing.

| Name | Means |
|------|--------|
| **Region** | One DOM slot (`class CartBadge(Region)` or `@ch.region`) |
| **RegionBook** | Channel registry of all slots (`ch.regions`) |
| **RegionDirectory** | Optional file/package discovery into that registry |

```text
Region = one slot · RegionBook = book of slots · you use Region every day
```

### What is a Region vs a Bridge vs an Action?

| | Region | Bridge | Action |
|--|--------|--------|--------|
| **Is** | Server-owned HTML slot | npm/JS island mount | Named mutation handler |
| **Does** | Re-paint via morph | Client widget lifecycle | Change truth, return Result |
| **Import** | `@ch.region` / `Region` | `ux_channel.bridges` | `@ch.on` / `@Region.action` |

Full decision table: [`python/ONTOLOGY.md`](python/ONTOLOGY.md).

### Why does `ux_channel` look like one huge flat folder?

Historical growth — **not** “one module does everything.” Each `.py` file is a focused unit; the directory listing is what feels flat. **Navigate by zone**, not alphabet:

```python
from ux_channel.zones import host, protocol
print(host.help())
```

Full map: [`python/LAYOUT.md`](python/LAYOUT.md). Apps still use `from ux_channel.host.day1 import Channel, Region`.

### Is the Python code stale / drifted from Rust?

No for the **protocol zone** (caps, wire, CXB, vectors). `make verify` + `make verify-http` (cross-mint) prove it. Optional planes (webrtc, bridges, …) are host-only and not required for Rust interop.

### How should new Python apps import the library?

```python
from ux_channel.host.day1 import Channel, ChannelConfig, Region, state, agents
```

Same objects as `from ux_channel import …`, but documents day-1 intent. See [`python/STRUCTURE.md`](python/STRUCTURE.md).

### What is ux-channel in one sentence?

A shared **Intent → Result + ops** contract so any peer (Python, Rust, …) can run actions under **capability tokens**, with **JSON always working** and optional denser binary (CXB).

---

### Is this REST?

Not classic REST-per-resource. You usually `POST /ux-channel/action` with an **Intent body**; `action` is a field (`Cart.add`), not a new URL per verb.

---

### What is the difference between an **action** and an **op**?

| | Action | Op |
|--|--------|-----|
| Side | Server (peer) | Client (surface) |
| Example | `Cart.add` | `toast`, `morph`, `signal_set` |
| When | Peer runs handler | Client applies Result.ops in order |

---

### What is a **cap**?

A signed **permission ticket** for one action + sealed args. It is not a login session for the whole app. See TERMINOLOGY → Cap.

---

### Why did my open `Counter.inc` fail with unauthorized?

You probably sent a `cap` field (even bogus). **Present-cap-must-verify:** any present cap is verified. Omit `cap` for open actions.

---

### Why is `"qty": "2"` rejected?

Integer fields reject non-integers on purpose (**no silent coercion**). Send `"qty": 2`.

---

### Why does health list `cxb` under codecs but not formats?

| Field | Meaning |
|-------|---------|
| `codecs` | Library can encode/decode CXB |
| `formats` | What HTTP **actually serves today** (JSON only until Accept negotiation) |

Advertising CXB on `formats` early would be a lie.

---

### Can I use `Accept: application/ux-channel+cxb` today?

**Not on Rust HTTP** yet. Codec is green in-library; negotiation is a known gap (HOW_IT_WORKS §8, README status).

---

### The peer won’t start — “UXC_CAP_SECRET is not set”

**Fail closed.** For local demo:

```bash
export UXC_ALLOW_ORACLE_SECRET=1
# or
export UXC_CAP_SECRET='your-private-high-entropy-secret'
```

Never use the public oracle secret in production. See [OPERATIONAL.md](OPERATIONAL.md).

---

### What is the oracle secret?

A **public** test secret in the repo so languages share golden cap tokens. Anyone can mint for it — that is why production must use a private secret.

---

### Is once/jti single-use working?

**SPEC requires it; Rust Cap 0.1 does not enforce yet.** Health reports `once_jti_enforced: false`. Do not build product features on single-use caps until that is green.

---

### Why escape toast/morph but not signal_set?

Display fields may be rendered as HTML (XSS risk). Signals are data for code. See INVARIANTS / TERMINOLOGY.

---

### HTTP 401 vs Result `unauthorized` — which do I use?

**Branch on Result** (`ok` / `error.code`). HTTP status is secondary for proxies/curl. This peer maps `unauthorized` → 401.

---

### Permanent vs moving — can I delete Cart.add?

Yes, **as a demo**, if permanent tests still pass. Do not delete SPEC, vectors, types, cap rules, or peer gate semantics without a major.

---

### How do I prove the tree is green?

```bash
make verify
make verify-http
```

This always runs **both** languages:
- Python: `pytest python/tests` (cap oracle, JSON + CXB vectors)
- Rust: `cargo test` + `uxc_check`
- Law harnesses + repo health

CI runs the same on every push.

---

### Where do I start reading?

1. [TERMINOLOGY.md](TERMINOLOGY.md)  
2. [HOW_IT_WORKS.md](HOW_IT_WORKS.md)  
3. [REFERENCE.md](REFERENCE.md)  
4. [OPERATIONAL.md](OPERATIONAL.md) before running the peer  

---

### Is the full Python package required?

No, for this **wire-native** tree. The zip is optional reference. Conformance harnesses are stdlib; Rust peer is self-contained; `python_forward` only needs stdlib (+ optional itsdangerous, or `--mint-via-peer`).
