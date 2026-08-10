# CXB — Channel eXchange Binary

**Status:** normative for ux-channel **0.1**  
**Format name:** `cxb`  
**Media type:** `application/ux-channel+cxb`  
**Aliases (Accept / Content-Type):** `application/cxb`  
**Magics:** `CXB1` (plain frame) · `CXBZ` (zlib-wrapped plain frame)  
**Layout version label:** `"1"` (not a header byte; documents the frame shape below)

This document is the **complete** specification of the CXB wire format, all
implementations in this repository, runtime selection, safety rules, HTTP
usage, and use cases. If a behavior is not described here, treat it as
undefined and open an issue — do not guess.

Related:

| Doc | Role |
|-----|------|
| [WIRE.md](./WIRE.md) | All wire formats (json/msgpack/cbor/cxb) |
| [CXB_SPEED.md](./CXB_SPEED.md) | Performance tiers / native strategy |
| [CXB_REALWORLD.md](./CXB_REALWORLD.md) | Size/latency on production-shaped fixtures |
| [WIRE_BENCH.md](./WIRE_BENCH.md) | Benchmark tables |
| [RESULT.md](./RESULT.md) | Result / ops semantics (IR, not bytes) |

---

## 1. Why CXB exists

Protobuf wins on **generic closed RPC** with codegen. ux-channel documents are:

- **Open** (`args`, `meta`, freeform ops)
- **Browser day-1** (JSON must work with zero codegen)
- **Op-centric** (shared Result.ops vocabulary across apps)

CXB is a **domain-native** binary for **Intent / Result / ops**:

| Concern | Protobuf | CXB |
|---------|----------|-----|
| Schema / codegen | Required | **None** — field registry in code |
| Browser day-1 | Needs wasm/codegen | JSON remains default; CXB opt-in |
| Open maps | Awkward `Struct` / `Any` | Freeform blobs (msgpack→JSON) |
| Op union | Oneof per service | Shared dense key tags 1–63 + free keys |
| Evolution | Field numbers | Fixed tags **+** extension map |
| Isomorphism | Binary-only | Same `dict` as JSON path |
| DX | Compile step | `encode(doc, format="cxb")` |

**Non-goals:** general RPC IDL, replacing JSON for browsers by default, multiplayer game netcode.

---

## 2. Day-1 application API (nothing else required)

```python
from ux_channel.wire import encode, decode, configure_wire

# Opt in for this process
configure_wire(format="cxb")

blob = encode(result_or_intent_dict)   # WireBlob: .data .media_type .format .engine
doc = decode(blob.data)                # dict

# Or per call without changing process default
blob = encode(doc, format="cxb")
doc = decode(blob.data, format="cxb")
```

Low-level (same bytes, same backends):

```python
from ux_channel.wire.cxb import (
    encode_cxb,
    decode_cxb,
    encode_cxb_python,   # force pure Python oracle
    decode_cxb_python,
    is_cxb,
    cxb_impl,            # "native" | "python"
    native_available,
    MAGIC,               # b"CXB1"
    MAGIC_Z,             # b"CXBZ"
    MEDIA_TYPE,          # application/ux-channel+cxb
    FORMAT_NAME,         # "cxb"
)
```

**Apps never register plugins for CXB.** The wire plugin registry is internal
(`ux_channel.wire.plugins`) for codec authors only.

---

## 3. Runtime backends (default vs optional)

| Backend | Location | Role |
|---------|----------|------|
| **Rust `.so` (default when built)** | [`cxb_native/cxb_rs/`](../../cxb_native/cxb_rs/) → `ux_channel._cxb_native` | CXB1 + CXBZ accelerator |
| **Pure Python (always shipped)** | [`src/ux_channel/wire/cxb.py`](../../src/ux_channel/wire/cxb.py) | Full oracle + safety fallback |

### 3.1 Selection rules

```text
encode_cxb / decode_cxb
  1. Read UX_CHANNEL_CXB_IMPL (default: auto)
  2. auto|native → use Rust _cxb_native if importable
  3. on any native exception → pure Python (never fail closed)
  4. python → pure Python only
```

| Env | Values | Effect |
|-----|--------|--------|
| `UX_CHANNEL_CXB_IMPL` | `auto` (default), `native`, `python` (`rust`→native, `py`→python) | Backend preference |

```bash
./cxb_native/build.sh    # build default Rust extension
```

```python
assert native_available()  # after build
assert cxb_impl() == "native"
```

`make_cxb_codec()` (internal wire registry) sets engine label:

- `cxb-native` when `cxb_impl() == "native"`
- `cxb` when pure Python is active

### 3.2 Monorepo note

A Rust crate **inside** the Python repo is intentional:

- One place for frame contract + CI + docs  
- Sdist works without Rust (Python oracle)  
- Wheels may ship the `.so`  
- Same crate can later grow a standalone peer binary  

See [`cxb_native/README.md`](../../cxb_native/README.md).

---

## 4. Frame layout (normative)

### 4.1 Plain frame — magic `CXB1` (4 bytes ASCII)

```text
 offset →
 ┌────────┬──────┬──────────────┬─────────┬────────────┬────────────┬──────────────────┐
 │ CXB1   │ kind │ string_table │ nfields │ fields…    │ extensions │ ~CRC ‖ u32be crc │
 │ 4 B    │ u8   │ §5           │ u16 BE  │ §6         │ §7         │ 4 + 4 B          │
 └────────┴──────┴──────────────┴─────────┴────────────┴────────────┴──────────────────┘
            ▲                                                              ▲
            payload start (CRC covers from here)                           integrity footer
```

### 4.2 Compressed frame — magic `CXBZ` (4 bytes ASCII)

```text
 ┌────────┬────────────────────────────────┐
 │ CXBZ   │ zlib stream of a full CXB1 frame│
 │ 4 B    │ (RFC 1950 zlib wrapper)         │
 └────────┴────────────────────────────────┘
```

Decode path:

1. If magic is `CXBZ`, `zlib.decompress(body)` (max expand §10).  
2. Result **must** start with `CXB1`.  
3. Continue as plain frame (including CRC check).

### 4.3 Document kind (`u8`)

| kind | Name | Meaning |
|-----:|------|---------|
| `1` | Intent | Request to run an action |
| `2` | Result | Outcome + ops to apply |
| `3` | Generic doc | Neither Intent nor Result shape |

**Encode classification** (implementations must match):

| Condition | kind |
|-----------|-----:|
| `"action" in doc` and `"ops" not in doc` | 1 Intent |
| `"ops" in doc` **or** (`"ok" in doc` and `"action" not in doc`) | 2 Result |
| else | 3 Generic |

Unknown kind on decode → error.

### 4.4 Endianness and integers

| Item | Encoding |
|------|----------|
| Multi-byte integers in headers | **Big-endian** unless noted |
| Varints | Unsigned LEB128 (protobuf-style): 7 data bits, high bit continuation |
| Signed integers in values | **Zigzag** then unsigned varint: `(n << 1) ^ (n >> 63)` for i64 |

---

## 5. String table (intern)

Immediately after `kind`:

```text
table_count: varint(n)
for i in 0..n-1:
    len_i: varint
    bytes_i: len_i octets of UTF-8
```

Indices are **0-based**. Wire type **10** (`W_INTERN`) references them as `u16 BE`.

### 5.1 Encode-side intern policy (normative for encoders that intern)

| Rule | Value |
|------|------:|
| Max distinct entries per message | 512 (`MAX_INTERN_ENTRIES`) |
| Max total UTF-8 bytes in table | 16 KiB (`MAX_INTERN_BYTES`) |
| Candidate string length | 1…128 (`INTERN_MIN_LEN`…`INTERN_MAX_LEN`) |
| Op-field candidate max length | 96 (`INTERN_OP_MAX_LEN`) |
| Minimum frequency to intern | **2** (`INTERN_MIN_FREQ`) |
| Payload keys never interned | `html`, `body`, `text`, `cap`, `bytes`, `payload`, `data` |

Selection: among strings with count ≥ 2, prefer **higher frequency**, then **shorter** length, until budgets exhaust.

**Rationale:** unique strings must not bloat the table; huge HTML must not displace useful tokens.

Decoders must accept any valid table (including empty) within decode ceilings (§10).

---

## 6. Known fields

```text
nfields: u16 big-endian
for _ in range(nfields):
    tag: u16 big-endian
    value: typed value (§8)   # includes its own type byte
```

### 6.1 Intent field tags (`kind == 1`)

| Tag | Key | Notes |
|----:|-----|-------|
| 1 | `v` | Protocol / doc version string (often `"1"`) |
| 2 | `action` | Action name, e.g. `Cart.add` |
| 3 | `args` | Typically freeform map (type 9) |
| 4 | `cap` | Capability token string (not interned as payload policy allows length) |
| 5 | `target` | Optional CSS / region selector |
| 6 | `request_id` | Correlation id |
| 7 | `form` | Optional form payload map |
| 8 | `accept_stream` | Bool |
| 9 | `idempotency_key` | Optional |
| 10 | `meta` | Freeform map |

Omitted keys are simply absent from the field list (no null required).

### 6.2 Result field tags (`kind == 2`)

| Tag | Key | Notes |
|----:|-----|-------|
| 1 | `v` | Version string |
| 2 | `ok` | Bool |
| 3 | `ops` | **Array** of op objects (usually type 11 opmap) |
| 4 | `error` | Freeform / structured error object |
| 5 | `meta` | Freeform map |

**Ops field encoding:** `tag=3` then a single value of type **array** (`7`), each element typically **opmap** (`11`).

### 6.3 Generic (`kind == 3`)

`nfields` should be `0`. Body content is carried via **extensions** (§7) only.

---

## 7. Extensions (open keys)

After known fields:

```text
n_ext: varint
for _ in range(n_ext):
    key_len: varint
    key: key_len UTF-8 bytes
    value: typed value (§8)
```

Any document key **not** listed in the Intent/Result tag tables is written here.
This is the primary evolution path for ad-hoc keys without minting new fixed tags.

---

## 8. Typed values (wire types)

Every value begins with a **type byte** (`u8`):

| Code | Name | Payload |
|-----:|------|---------|
| 0 | `null` | — |
| 1 | `false` | — |
| 2 | `true` | — |
| 3 | `varint` | zigzag-signed integer as unsigned LEB128 |
| 4 | `f64` | 8 bytes IEEE-754 **big-endian** |
| 5 | `utf8` | `varint(len)` ‖ UTF-8 bytes |
| 6 | `bytes` | `varint(len)` ‖ raw octets |
| 7 | `array` | `varint(n)` ‖ `n` × typed value |
| 8 | `map` | reserved / rarely used; prefer freeform (9) for open dicts |
| 9 | `freeform` | `varint(len)` ‖ blob (§8.1) |
| 10 | `intern` | `u16 BE` index into string table |
| 11 | `opmap` | dense op object (§9) |

Unknown type byte → decode error.

### 8.1 Freeform blob (type 9)

Used for open dicts (`args`, `meta`, nested maps, oversized op maps).

**Encode preference:**

1. If `msgpack` is importable: `msgpack.packb(obj, use_bin_type=True)`  
2. Else: `json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`

**Decode preference:**

1. Try msgpack unpack (if available)  
2. Else UTF-8 JSON  

Interoperability note: a pure-JSON freeform blob is always valid; msgpack is denser when both peers have it.

### 8.2 Booleans vs integers

Encoders must emit type `1`/`2` for JSON/Python booleans, **not** integer 0/1 as varint. Decoders distinguish bool wire types from integers.

---

## 9. Op map (type 11) — Result ops

```text
0x0B
nkeys: u8                    # 0..255; if more keys needed, use freeform map instead
for _ in range(nkeys):
    key_header
    value: typed value
```

### 9.1 Key header

| Form | Encoding |
|------|----------|
| Dense known key | single `u8` in **1..63** |
| Free (unknown) key | `0xFF` ‖ `varint(len)` ‖ UTF-8 key name |

### 9.2 Dense op key tags (1–63) — complete registry

**Stable and append-only.** Never reuse a number for a different name.
Unknown tags on decode may surface as `ext:<n>` or be rejected by strict tools;
the Python oracle maps unknown dense tags via reverse table only for known ids.

| Tag | Key | Tag | Key | Tag | Key |
|----:|-----|----:|-----|----:|-----|
| 1 | `op` | 22 | `replace` | 43 | `style` |
| 2 | `target` | 23 | `swap` | 44 | `dataset` |
| 3 | `html` | 24 | `settle_ms` | 45 | `component` |
| 4 | `message` | 25 | `attrs` | 46 | `slot` |
| 5 | `level` | 26 | `select` | 47 | `key` |
| 6 | `morph` | 27 | `top` | 48 | `children` |
| 7 | `url` | 28 | `left` | 49 | `mime` |
| 8 | `selector` | 29 | `behavior` | 50 | `filename` |
| 9 | `value` | 30 | `bubbles` | 51 | `bytes` |
| 10 | `name` | 31 | `package` | 52 | `encoding` |
| 11 | `path` | 32 | `props` | 53 | `payload` |
| 12 | `detail` | 33 | `args` | 54 | `data` |
| 13 | `duration_ms` | 34 | `meta` | 55 | `config` |
| 14 | `method` | 35 | `code` | 56 | `options` |
| 15 | `headers` | 36 | `reason` | 57 | `params` |
| 16 | `status` | 37 | `dropped` | 58 | `context` |
| 17 | `id` | 38 | `retryable` | 59 | `source` |
| 18 | `text` | 39 | `stream` | 60 | `channel` |
| 19 | `title` | 40 | `seq` | 61 | `region` |
| 20 | `body` | 41 | `ts` | 62 | `version` |
| 21 | `href` | 42 | `class` | 63 | `type` |

**`op` values are free strings** (`"toast"`, `"morph"`, `"bridge.mount"`, `"my.plugin.x"`).
There is **no** enum of allowed op types at the wire layer.

### 9.3 Op map limits

| Rule | Limit |
|------|------:|
| Max dense+free keys in one opmap | 255 (u8 count) |
| More keys | Encode whole op as freeform map (type 9) |

---

## 10. CRC integrity footer

Every **plain** `CXB1` frame ends with:

```text
ASCII 0x7E 0x43 0x52 0x43     # "~CRC"
u32 big-endian                # CRC-32
```

| Item | Spec |
|------|------|
| Algorithm | ISO/IEEE CRC-32 (same as Python `zlib.crc32` / zlib) |
| Coverage | All bytes **after** the 4-byte magic through the last extension byte (**excluding** the 8-byte footer) |
| On mismatch | Decode **must** raise / fail (no silent accept) |
| Legacy frames without footer | Not produced by 0.1 encoders; decoders that require CRC should reject |

When the outer magic is `CXBZ`, CRC applies to the **inner** inflated `CXB1` frame.

---

## 11. CXBZ compression policy (encode)

After a complete plain frame (with CRC) is built:

```text
if len(plain) < 384: keep CXB1
else:
    comp = zlib.compress(plain, level=6)
    zlen = len(comp) + 4   # CXBZ magic
    saved = len(plain) - zlen
    if saved >= 48 and (len(plain) / zlen) >= 1.20:
        emit CXBZ ‖ comp
    else:
        emit plain CXB1
```

| Constant | Value | Meaning |
|----------|------:|---------|
| `CXBZ_MIN_PLAIN` | 384 | Do not consider smaller frames |
| `CXBZ_MIN_SAVE` | 48 | Minimum bytes saved (incl. magic) |
| `CXBZ_MIN_RATIO` | 1.20 | Minimum plain/compressed ratio |
| `CXBZ_ZLIB_LEVEL` | 6 | zlib compression level |

If not smaller enough → **keep CXB1** (never emit a larger “compressed” frame).

---

## 12. Resource ceilings (decode)

| Ceiling | Limit | Constant |
|---------|------:|----------|
| Nest depth | 64 | `MAX_NEST_DEPTH` |
| Array length | 1_000_000 | `MAX_ARRAY_LEN` |
| Known field count | 100_000 | `MAX_FIELDS` |
| String table entries | 100_000 | `MAX_STRING_TABLE` |
| Single blob / freeform / zlib expand | 32 MiB | `MAX_BLOB` |

Exceeding a ceiling → hard error. Protects against zip-bombs and hostile frames.

---

## 13. Encode / decode algorithms (normative behavior)

### 13.1 Encode (both backends)

1. **Snapshot** input (deep copy of dict/list structure) so concurrent mutation cannot tear a frame.  
2. Classify kind (§4.3).  
3. Frequency-scan eligible strings; build intern allow-set (§5.1).  
4. Write magic `CXB1`, kind, string table, fields, extensions.  
5. Append `~CRC` + crc32.  
6. Optionally wrap as `CXBZ` (§11).  

Custom `default=` for non-JSON types: pure Python path supports it; native path requires `default is str` (the normal case) or falls back to Python.

### 13.2 Decode (both backends)

1. Reject if not `is_cxb` (magic `CXB1` or `CXBZ`).  
2. Prefer native if selected and available; on failure → Python.  
3. Inflate CXBZ if needed.  
4. Verify CRC if footer present.  
5. Parse table, fields, extensions into a `dict`.  

### 13.3 Concurrency

| Guarantee | Mechanism |
|-----------|-----------|
| Thread-safe encode/decode | No shared mutable encoder; per-call buffers |
| No torn frames | Input snapshot |
| Process policy | Wire `configure_wire` is locked; CXB backend env is read per call |

---

## 14. HTTP / WebSocket usage

### 14.1 Media type

```http
Content-Type: application/ux-channel+cxb
Accept: application/ux-channel+cxb, application/ux-channel+json;q=0.9
```

Negotiation is handled by `ux_channel.wire.negotiate` / ASGI helpers. If the peer cannot speak CXB, JSON is the floor.

### 14.2 Body

- Request Intent: raw CXB bytes (not base64).  
- Response Result: raw CXB bytes.  
- Charset parameters are ignored (binary).

### 14.3 Sniffing

`is_cxb(data)` / wire sniff: first 4 bytes ∈ {`CXB1`, `CXBZ`}.

### 14.4 Complete recovery

Wire `decode(..., complete=True)` (default): if preferred format fails, try magic sniff and other available formats so a mislabeled body can still complete the action when possible.

---

## 15. Implementations in this repository

### 15.1 Pure Python oracle

| Item | Path |
|------|------|
| Module | `src/ux_channel/wire/cxb.py` |
| Encode | `encode_cxb_python` |
| Decode | `decode_cxb_python` |
| Role | Reference semantics, always available, fallback |

### 15.2 Rust accelerator (default when built)

| Item | Path |
|------|------|
| Crate | `cxb_native/cxb_rs/` |
| Build | `./cxb_native/build.sh` |
| Module | `ux_channel._cxb_native` (`encode` / `decode`) |
| Op tags | `cxb_native/cxb_rs/src/op_tags.rs` (**must match** Python `_OP_KEY_TAGS`) |
| Features | CXB1 + CXBZ + CRC + ceilings |


| Item | Path |
|------|------|
| Features | CXB1 + CRC; **no CXBZ** |
| Status | Not the default build; kept for experiments |

### 15.4 Wire integration

| Item | Path |
|------|------|
| Plugin bootstrap | `src/ux_channel/wire/core.py` registers format `cxb` |
| Public exports | `src/ux_channel/wire/__init__.py` |
| Internal plugins API | `src/ux_channel/wire/plugins.py` |

### 15.5 Tests (do not skip when changing the format)

| Suite | Path | Intent |
|-------|------|--------|
| Backends | `tests/core/test_cxb_backends.py` | native default, force python, cross decode |
| Native module | `tests/core/test_cxb_native.py` | `.so` roundtrip, CXBZ, CRC reject |
| CXB unit | `tests/core/test_wire_cxb.py` | HTTP Accept, configure, ops |
| Intern safety | `tests/core/test_wire_cxb_intern.py` | no intern side-effects |
| Realworld | `tests/core/test_wire_cxb_realworld.py` | production-shaped fixtures |
| Conformance | `tests/core/test_wire_conformance_live.py` | live ASGI + formats |
| Properties | `tests/core/test_wire_properties.py` | Hypothesis |
| Fuzz | `tests/core/test_wire_fuzz.py` / `scripts/fuzz_wire.py` | mutational |

```bash
./cxb_native/build.sh
PYTHONPATH=src pytest tests/core/test_cxb_*.py tests/core/test_wire_cxb*.py -q
```

### 15.6 Examples & benches

| Artifact | Path |
|----------|------|
| Demo | `examples/cxb_wire/` |
| Realworld bench | `scripts/bench_cxb_realworld.py` |
| Wire bench | `scripts/bench_wire.py` |

---

## 16. Use cases (when to use CXB)

### 16.1 Use CXB when

| Use case | Why CXB helps |
|----------|----------------|
| **Server ↔ server** Intent/Result | Dense multi-op Results, no browser |
| **Python ↔ Rust peer / sidecar** | Same IR bytes, no JSON tax |
| **Bulk toasts / multi-region morphs** | Intern + CXBZ on repetition |
| **Large HTML morph payloads** | CXBZ when compressible |
| **Mesh / UDS / worker hops** | Binary frames + CRC integrity |
| **High QPS internal APIs** | Lower encode/decode + bandwidth |

### 16.2 Prefer JSON when

| Use case | Why JSON |
|----------|----------|
| **Browser day-1** | Zero WASM, debuggable DevTools |
| **Public APIs / curl** | Universal tooling |
| **Tiny single-field docs** | CXB header overhead not worth it |
| **Human debugging** | Readable bodies |

### 16.3 Hybrid pattern (recommended production)

```text
Browser  ── JSON ──▶  Channel host (Python)
                         │
                         │ CXB (UDS/HTTP) optional
                         ▼
                    Rust worker / WASM peer
                         │
                    Result (CXB)
                         │
Browser  ◀── JSON ──  (host may re-encode for Accept)
```

Or end-to-end CXB when the client is a native/mesh peer that speaks the media type.

### 16.4 What CXB is **not** for

- Arbitrary file transfer (use bytes fields carefully; 32 MiB ceiling)  
- Replacing capability security (caps are still verified at IR layer)  
- Storing long-term archives without versioning discipline  
- Cross-vendor APIs that do not implement this spec  

---

## 17. Worked examples

### 17.1 Intent (plain CXB1)

```python
doc = {
    "v": "1",
    "action": "Cart.add",
    "args": {"sku": "a", "qty": 2},
    "cap": "<capability-token>",
    "request_id": "r1",
}
raw = encode_cxb(doc)
assert raw[:4] == b"CXB1"
assert raw[-8:-4] == b"~CRC"
assert decode_cxb(raw)["action"] == "Cart.add"
```

Logical layout:

```text
CXB1 | kind=1 | table | nfields | (v)(action)(args)(cap)(request_id) | ext=0 | ~CRC|crc
```

### 17.2 Result with ops

```python
from ux_channel import ops as O

doc = {
    "v": "1",
    "ok": True,
    "ops": [
        O.toast("Saved", level="success"),
        O.morph("#cart", "<div>…</div>"),
    ],
    "meta": {"action": "Cart.add"},
}
raw = encode_cxb(doc)
back = decode_cxb(raw)
assert back["ops"][0]["op"] == "toast"
```

Ops use type **11** with dense keys `op=1`, `message=4`, `level=5`, `target=2`, `html=3`, `morph=6`, etc.

### 17.3 Bulk → often CXBZ

```python
doc = {"v": "1", "ok": True, "ops": [O.toast("Saved", level="success")] * 40}
raw = encode_cxb(doc)
# frequently b"CXBZ" when gates pass
assert is_cxb(raw)
assert len(decode_cxb(raw)["ops"]) == 40
```

### 17.4 Force Python oracle

```python
import os
os.environ["UX_CHANNEL_CXB_IMPL"] = "python"
from ux_channel.wire.cxb import encode_cxb, cxb_impl
assert cxb_impl() == "python"
# or call encode_cxb_python explicitly without env
```

---

## 18. Interoperability checklist (multi-impl)

An implementation is CXB-compatible when it:

- [ ] Emits/accepts magics `CXB1` / `CXBZ`  
- [ ] Uses kind 1/2/3 classification above  
- [ ] Implements all value types 0–11 used by peers (unknown → error)  
- [ ] Implements Intent tags 1–10 and Result tags 1–5  
- [ ] Implements op dense tags **exactly** as §9.2 (or only free keys, which is denser-worse but valid)  
- [ ] Writes and verifies `~CRC` as §10  
- [ ] Applies CXBZ gates when compressing (§11) or never compresses (always CXB1 is valid)  
- [ ] Enforces ceilings (§10)  
- [ ] Round-trips the golden fixtures in `tests/core/test_wire_cxb*.py`  

Python `encode_cxb_python` / `decode_cxb_python` is the **oracle** for disputes.

---

## 19. Versioning and evolution

| Change type | Allowed? | How |
|-------------|----------|-----|
| New op dense tag 64+ | Needs layout revision | Not in 0.1 (max 63) |
| New Intent/Result tag | Additive if decoders ignore unknown tags | Prefer extensions for experimental keys |
| New free `op` string | Always | No wire change |
| New free op key name | Always | `0xFF` free key |
| Change meaning of existing tag | **Forbidden** | Mint a new tag |
| CRC algorithm change | **Forbidden** for magic CXB1 | New magic required |
| CXBZ algorithm change | **Forbidden** for magic CXBZ | New magic required |

Process: bump docs + golden tests in the same PR; sync `op_tags.rs` with `_OP_KEY_TAGS`.

---

## 20. Security considerations

| Threat | Mitigation |
|--------|------------|
| Bit-flip / corruption | CRC footer |
| Zip bomb | `MAX_BLOB` on inflate |
| Deep recursion | `MAX_NEST_DEPTH` |
| Huge arrays | `MAX_ARRAY_LEN` |
| Table bomb | table ceilings + intern encode budgets |
| Confused deputy | Caps verified at IR layer **before** trusting action (not part of CXB bytes) |
| Native memory bugs | Exception → Python fallback; keep oracle in CI |

CXB does **not** encrypt or authenticate. Use TLS and capability tokens.

---

## 21. Quick reference card

```text
Media:  application/ux-channel+cxb
Magic:  CXB1 | CXBZ
Kind:   1 Intent · 2 Result · 3 Doc
Value:  0null 1false 2true 3varint 4f64 5utf8 6bytes 7array 8map 9free 10intern 11opmap
Op key: 1..63 dense · 0xFF free
Footer: ~CRC ‖ u32be zlib-crc32(payload after magic)
CXBZ:   only if len≥384 and save≥48 and ratio≥1.20 at zlib-6
API:    encode(..., format="cxb")  ·  UX_CHANNEL_CXB_IMPL=auto|native|python
Build:  ./cxb_native/build.sh
Oracle: encode_cxb_python / decode_cxb_python
```

---

## 22. Source of truth map

| Concern | Source of truth |
|---------|-----------------|
| This document | Human-facing complete spec |
| Encode/decode semantics | `src/ux_channel/wire/cxb.py` |
| Dense op tags | `_OP_KEY_TAGS` in `cxb.py` ↔ `op_tags.rs` |
| Default speed path | `cxb_native/cxb_rs` via `_cxb_native` |
| Wire policy / HTTP | `src/ux_channel/wire/core.py`, `negotiate.py` |
| Tests | `tests/core/test_cxb_*.py`, `tests/core/test_wire_cxb*.py` |

If code and this doc disagree, **fix the code and update this doc in the same change**.
