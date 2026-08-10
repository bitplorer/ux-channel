# Copyright (c) 2026 UX-CHANNEL
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
"""**CXB** — Channel eXchange Binary (``format="cxb"``).
Why this exists (vs protobuf)
Protobuf wins on *generic* RPC when you own a closed schema and a codegen
pipeline. **ux-channel** documents are open (args, meta, freeform ops) and
must speak **JSON to browsers on day‑1** with **zero codegen**.
CXB is a **domain-native** binary for Intent / Result / ops that aims to be
*better than protobuf…"""

from __future__ import annotations

import json
import os
import struct
from typing import Any, Callable, Mapping, Optional, Sequence

__all__ = [
    "FORMAT_NAME",
    "MAGIC",
    "MAGIC_Z",
    "MEDIA_TYPE",
    "VERSION_LABEL",
    "cxb_impl",
    "decode_cxb",
    "decode_cxb_python",
    "encode_cxb",
    "encode_cxb_python",
    "is_cxb",
    "make_cxb_codec",
    "native_available",
]

MAGIC = b"CXB1"  # uncompressed frame
MAGIC_Z = b"CXBZ"  # zlib-wrapped full frame (optional size win)
VERSION_LABEL = "1"
MEDIA_TYPE = "application/ux-channel+cxb"
FORMAT_NAME = "cxb"

# CXBZ tradeoffs (encode):
# * Only consider frames >= CXBZ_MIN_PLAIN (zlib header overhead on tiny frames).
# * Require CXBZ_MIN_SAVE bytes *and* CXBZ_MIN_RATIO — skips high-entropy
#   "barely smaller" wraps that tax decode more than they help the wire.
# * zlib level 6: good size; level 1 is ~2× faster compress with near-equal size
#   on repetitive HTML (see docs/core/CXB.md).
CXBZ_MIN_PLAIN = 384
CXBZ_MIN_SAVE = 48          # absolute bytes saved (includes 4B magic)
CXBZ_MIN_RATIO = 1.20       # plain / compressed >= 1.15
CXBZ_ZLIB_LEVEL = 6

MAX_STRING_TABLE = 100_000  # decode ceiling
MAX_FIELDS = 100_000
MAX_NEST_DEPTH = 64
MAX_ARRAY_LEN = 1_000_000
MAX_BLOB = 32 * 1024 * 1024  # 32 MiB single blob / decompress

# Encode-side interning budgets (prevent side-effect bloat / O(n) surprises)
MAX_INTERN_ENTRIES = 512       # distinct interned strings per message
MAX_INTERN_BYTES = 16 * 1024   # utf-8 payload bytes in the string table
INTERN_MIN_LEN = 1
INTERN_MAX_LEN = 128           # hard cap — longer always inline
INTERN_OP_MAX_LEN = 96         # ops: slightly stricter
INTERN_MIN_FREQ = 2            # only intern if appears 2+ times (no unique-table tax)

# kind
_KIND_INTENT = 1
_KIND_RESULT = 2
_KIND_DOC = 3

# wire types
_W_NULL = 0
_W_FALSE = 1
_W_TRUE = 2
_W_VARINT = 3
_W_F64 = 4
_W_UTF8 = 5
_W_BYTES = 6
_W_ARRAY = 7
_W_MAP = 8
_W_FREE = 9
_W_INTERN = 10
_W_OPMAP = 11  # dense op object: u8-tagged keys

# Intent field tags (stable — never renumber)
_I_V = 1
_I_ACTION = 2
_I_ARGS = 3
_I_CAP = 4
_I_TARGET = 5
_I_REQUEST_ID = 6
_I_FORM = 7
_I_ACCEPT_STREAM = 8
_I_IDEMPOTENCY = 9
_I_META = 10

# Result field tags
_R_V = 1
_R_OK = 2
_R_OPS = 3
_R_ERROR = 4
_R_META = 5

# ErrorObject
_E_CODE = 1
_E_MESSAGE = 2
_E_FIELDS = 3
_E_RETRYABLE = 4
_E_DETAILS = 5

# Op keys: tags 1–63 dense; 0xFF free-key for unknown names.

_OP_KEY_TAGS: dict[str, int] = {
    # core
    "op": 1,
    "target": 2,
    "html": 3,
    "message": 4,
    "level": 5,
    "morph": 6,
    "url": 7,
    "selector": 8,
    "value": 9,
    "name": 10,
    "path": 11,
    "detail": 12,
    "duration_ms": 13,
    "method": 14,
    "headers": 15,
    "status": 16,
    "id": 17,
    "text": 18,
    "title": 19,
    "body": 20,
    # navigation / history
    "href": 21,
    "replace": 22,
    # swap / settle
    "swap": 23,
    "settle_ms": 24,
    # attributes / focus / scroll
    "attrs": 25,
    "select": 26,
    "top": 27,
    "left": 28,
    "behavior": 29,
    # events
    "bubbles": 30,
    # bridge
    "package": 31,
    "props": 32,
    "args": 33,
    # universal extension bag
    "meta": 34,
    # errors / diagnostics sometimes embedded on ops
    "code": 35,
    "reason": 36,
    "dropped": 37,
    "retryable": 38,
    # streaming / timing extras
    "stream": 39,
    "seq": 40,
    "ts": 41,
    # CSS / class helpers (future-friendly)
    "class": 42,
    "style": 43,
    "dataset": 44,
    # component / slot (future UI ops)
    "component": 45,
    "slot": 46,
    "key": 47,
    "children": 48,
    # binary / file-ish
    "mime": 49,
    "filename": 50,
    "bytes": 51,
    "encoding": 52,
    # generic payload bags used by plugins
    "payload": 53,
    "data": 54,
    "config": 55,
    "options": 56,
    "params": 57,
    "context": 58,
    "source": 59,
    "channel": 60,
    "region": 61,
    "version": 62,
    "type": 63,
}
_OP_TAG_KEYS: dict[int, str] = {v: k for k, v in _OP_KEY_TAGS.items()}
_OP_FREE_KEY = 0xFF
_OP_MAX_DENSE_KEYS = 255

# Intent/result known key sets for classification
_INTENT_KEYS = frozenset(
    {
        "v",
        "action",
        "args",
        "cap",
        "target",
        "request_id",
        "form",
        "accept_stream",
        "idempotency_key",
        "meta",
    }
)
_RESULT_KEYS = frozenset({"v", "ok", "ops", "error", "meta"})


# Freeform blob (msgpack preferred)


_MSGPACK = None
try:
    import msgpack as _MSGPACK  # type: ignore
except ImportError:
    _MSGPACK = None


def _free_dumps(obj: Any, default: Callable[[Any], Any]) -> bytes:
    if _MSGPACK is not None:
        try:
            return _MSGPACK.packb(obj, default=default, use_bin_type=True)
        except Exception:
            pass
    return json.dumps(
        obj, default=default, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _free_loads(data: bytes) -> Any:
    """Decode free-form nested payload (msgpack preferred; JSON fallback).

    Golden CXB blobs use msgpack free-form; CI must install ``msgpack``.
    """
    if not data:
        return None
    if _MSGPACK is not None:
        try:
            return _MSGPACK.unpackb(data, raw=False, strict_map_key=False)
        except Exception:
            pass
    try:
        return json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(
            "CXB free-form payload is not UTF-8 JSON; install msgpack "
            "(required for oracle/golden decode)"
        ) from exc


# Varint (protobuf-style zigzag for signed ints)


def _write_varint(buf: bytearray, n: int) -> None:
    # unsigned varint
    if n < 0:
        raise ValueError("varint unsigned only — use zigzag")
    while n > 0x7F:
        buf.append((n & 0x7F) | 0x80)
        n >>= 7
    buf.append(n & 0x7F)


def _read_varint(mv: memoryview, i: int) -> tuple[int, int]:
    shift = 0
    n = 0
    while True:
        if i >= len(mv):
            raise ValueError("truncated varint")
        b = mv[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not (b & 0x80):
            return n, i
        shift += 7
        if shift > 70:
            raise ValueError("varint too long")


def _zigzag_encode(n: int) -> int:
    return (n << 1) ^ (n >> 63)


def _zigzag_decode(n: int) -> int:
    return (n >> 1) ^ (-(n & 1))


# Encoder


class _Enc:
    """Per-call encoder. String table is message-local; never shared across threads."""

    __slots__ = ("buf", "default", "table", "index", "table_bytes", "allow")

    def __init__(
        self,
        default: Callable[[Any], Any],
        *,
        allow: Optional[set[str]] = None,
    ):
        self.buf = bytearray()
        self.default = default
        self.table: list[str] = []
        self.index: dict[str, int] = {}
        self.table_bytes = 0
        # None = allow any candidate (still subject to budgets + length)
        # set = only these strings (frequency-filtered)
        self.allow = allow

    def try_intern(self, s: str) -> Optional[int]:
        """Return table index or None → caller must write inline utf8.

        Guarantees:
        * no intern if string not in allow-set (freq < 2)
        * no intern past MAX_INTERN_ENTRIES / MAX_INTERN_BYTES
        * no intern outside INTERN_MIN_LEN..INTERN_MAX_LEN
        * never mutates a shared/global table
        """
        if not (INTERN_MIN_LEN <= len(s) <= INTERN_MAX_LEN):
            return None
        if self.allow is not None and s not in self.allow:
            return None
        i = self.index.get(s)
        if i is not None:
            return i
        if len(self.table) >= MAX_INTERN_ENTRIES:
            return None
        raw_len = len(s.encode("utf-8"))
        if self.table_bytes + raw_len > MAX_INTERN_BYTES:
            return None
        i = len(self.table)
        self.table.append(s)
        self.index[s] = i
        self.table_bytes += raw_len
        return i

    def write_table(self) -> None:
        _write_varint(self.buf, len(self.table))
        for s in self.table:
            raw = s.encode("utf-8")
            _write_varint(self.buf, len(raw))
            self.buf.extend(raw)

    def w_tag(self, tag: int, wire: int) -> None:
        self.buf.extend(struct.pack(">HB", tag & 0xFFFF, wire & 0xFF))

    def w_utf8(self, s: str, *, intern: bool = False) -> None:
        if intern:
            idx = self.try_intern(s)
            if idx is not None:
                self.buf.append(_W_INTERN)
                self.buf.extend(struct.pack(">H", idx))
                return
        raw = s.encode("utf-8")
        self.buf.append(_W_UTF8)
        _write_varint(self.buf, len(raw))
        self.buf.extend(raw)

    def w_bytes(self, b: bytes) -> None:
        self.buf.append(_W_BYTES)
        _write_varint(self.buf, len(b))
        self.buf.extend(b)

    def w_value(self, v: Any, *, intern_str: bool = False) -> None:
        if v is None:
            self.buf.append(_W_NULL)
            return
        if v is False:
            self.buf.append(_W_FALSE)
            return
        if v is True:
            self.buf.append(_W_TRUE)
            return
        if isinstance(v, bool):  # pragma: no cover — bool is int subclass
            self.buf.append(_W_TRUE if v else _W_FALSE)
            return
        if isinstance(v, int) and not isinstance(v, bool):
            self.buf.append(_W_VARINT)
            _write_varint(self.buf, _zigzag_encode(int(v)))
            return
        if isinstance(v, float):
            self.buf.append(_W_F64)
            self.buf.extend(struct.pack(">d", float(v)))
            return
        if isinstance(v, str):
            if intern_str:
                idx = self.try_intern(v)
                if idx is not None:
                    self.buf.append(_W_INTERN)
                    self.buf.extend(struct.pack(">H", idx))
                    return
            raw = v.encode("utf-8")
            self.buf.append(_W_UTF8)
            _write_varint(self.buf, len(raw))
            self.buf.extend(raw)
            return
        if isinstance(v, (bytes, bytearray)):
            self.w_bytes(bytes(v))
            return
        vt = type(v)
        if vt is list or vt is tuple:
            self.buf.append(_W_ARRAY)
            _write_varint(self.buf, len(v))
            for item in v:
                self.w_value(item, intern_str=True)
            return
        if vt is dict or isinstance(v, Mapping):
            blob = _free_dumps(dict(v), self.default)
            self.buf.append(_W_FREE)
            _write_varint(self.buf, len(blob))
            self.buf.extend(blob)
            return
        # fallback
        try:
            s = self.default(v)
        except Exception:
            s = str(v)
        self.w_value(s)

    def w_field(self, tag: int, v: Any, *, intern_str: bool = False) -> None:
        """Write tag + value (value includes its wire type)."""
        # reserve tag; value writer includes wire type as first byte
        # layout: tag:u16 | value...
        start = len(self.buf)
        self.buf.extend(struct.pack(">H", tag & 0xFFFF))
        self.w_value(v, intern_str=intern_str)
        # value's first byte is wire type — already written by w_value


def _is_intent(doc: Mapping[str, Any]) -> bool:
    return "action" in doc and "ops" not in doc


def _is_result(doc: Mapping[str, Any]) -> bool:
    return "ops" in doc or ("ok" in doc and "action" not in doc)


def _encode_error(enc: _Enc, err: Mapping[str, Any]) -> bytes:
    """Error object as freeform blob (small, open shape)."""
    return _free_dumps(dict(err), enc.default)


def _deep_snapshot_value(v: Any) -> Any:
    """Snapshot nested values. Fast path for plain dict/list (no typing.Mapping)."""
    vt = type(v)
    if vt is dict:
        return {k if type(k) is str else str(k): _deep_snapshot_value(x) for k, x in v.items()}
    if vt is list:
        return [_deep_snapshot_value(x) for x in v]
    if vt is tuple:
        return [_deep_snapshot_value(x) for x in v]
    if isinstance(v, Mapping):  # rare subtypes
        return {str(k): _deep_snapshot_value(x) for k, x in v.items()}
    return v


def _encode_one_op(enc: _Enc, op: Mapping[str, Any]) -> None:
    """Encode a single op map: dense OPMAP, or freeform if too wide.

    Ops are already snapshotted at the document root — do not deep-copy again.
    """
    items = list(op.items()) if type(op) is dict else [(str(k), v) for k, v in op.items()]
    if len(items) > _OP_MAX_DENSE_KEYS:
        enc.w_value({k: v for k, v in items})
        return
    enc.buf.append(_W_OPMAP)
    enc.buf.append(len(items) & 0xFF)
    for ks, v in items:
        tag = _OP_KEY_TAGS.get(ks, 0)
        if 1 <= tag <= 63:
            enc.buf.append(tag & 0xFF)
        else:
            enc.buf.append(_OP_FREE_KEY)
            raw = ks.encode("utf-8")
            if len(raw) > MAX_BLOB:
                raise ValueError("op key too large")
            _write_varint(enc.buf, len(raw))
            enc.buf.extend(raw)
        intern = not (
            ks in ("html", "body", "text", "cap", "bytes", "payload", "data")
            or (isinstance(v, str) and len(v) > INTERN_OP_MAX_LEN)
            or isinstance(v, (bytes, bytearray))
        )
        enc.w_value(v, intern_str=intern)


def _encode_ops(enc: _Enc, ops: Sequence[Any]) -> None:
    """Write ops array (dense tags + free-key unknowns)."""
    enc.buf.append(_W_ARRAY)
    _write_varint(enc.buf, len(ops))
    for op in ops:
        ot = type(op)
        if ot is not dict and not isinstance(op, Mapping):
            enc.w_value(op)
            continue
        try:
            _encode_one_op(enc, op)
        except Exception:
            enc.w_value(dict(op) if ot is dict else dict(op))


def _snapshot_for_cxb(doc: Any) -> Any:
    """Isolate encode from concurrent mutation of the caller's structure."""
    vt = type(doc)
    if vt is dict or vt is list or vt is tuple:
        return _deep_snapshot_value(doc)
    if isinstance(doc, Mapping):
        return _deep_snapshot_value(doc)
    return doc


def _note_str(freq: dict[str, int], s: str, *, max_len: int = INTERN_MAX_LEN) -> None:
    if INTERN_MIN_LEN <= len(s) <= max_len:
        freq[s] = freq.get(s, 0) + 1


def _collect_string_freq(doc: Mapping[str, Any]) -> dict[str, int]:
    """Count intern-candidate strings with the same rules as encode (no side tables)."""
    freq: dict[str, int] = {}

    def walk_val(v: Any, *, intern_ok: bool, max_len: int = INTERN_MAX_LEN) -> None:
        if isinstance(v, str):
            if intern_ok:
                _note_str(freq, v, max_len=max_len)
            return
        if isinstance(v, (list, tuple)):
            for item in v:
                walk_val(item, intern_ok=True, max_len=max_len)
            return
        # mappings as freeform — not in CXB string table
        return

    if _is_intent(doc):
        for key, intern_ok in (
            ("v", True),
            ("action", True),
            ("target", True),
            ("request_id", True),
            ("idempotency_key", True),
        ):
            if key in doc and isinstance(doc[key], str):
                walk_val(doc[key], intern_ok=intern_ok)
    elif _is_result(doc):
        if isinstance(doc.get("v"), str):
            walk_val(doc["v"], intern_ok=True)
        ops = doc.get("ops")
        if isinstance(ops, (list, tuple)):
            for op in ops:
                if not isinstance(op, Mapping):
                    walk_val(op, intern_ok=True)
                    continue
                for ks, v in op.items():
                    if ks in ("html", "body", "text", "cap", "bytes", "payload", "data"):
                        continue
                    if isinstance(v, str):
                        walk_val(v, intern_ok=True, max_len=INTERN_OP_MAX_LEN)
                    elif isinstance(v, (list, tuple)):
                        walk_val(v, intern_ok=True, max_len=INTERN_OP_MAX_LEN)
    else:
        # generic doc — light touch: top-level short strings only
        for v in doc.values():
            if isinstance(v, str):
                walk_val(v, intern_ok=True)
    return freq


def _allow_set_from_freq(freq: dict[str, int]) -> set[str]:
    """Strings that appear often enough, under table budgets (high-freq first)."""
    ranked = sorted(
        ((c, -len(s), s) for s, c in freq.items() if c >= INTERN_MIN_FREQ),
        reverse=True,
    )
    allow: set[str] = set()
    nbytes = 0
    for c, _neg_len, s in ranked:
        if len(allow) >= MAX_INTERN_ENTRIES:
            break
        bl = len(s.encode("utf-8"))
        if nbytes + bl > MAX_INTERN_BYTES:
            continue
        allow.add(s)
        nbytes += bl
    return allow


# Runtime: Rust ``_cxb_native`` (default) + pure Python (optional fallback)
# The Rust crate lives in-repo at ``cxb_native/cxb_rs/`` and builds the extension
# module ``ux_channel._cxb_native`` (CXB1 + CXBZ). Pure Python below is the
# full reference implementation and safety net.
#
# Env: UX_CHANNEL_CXB_IMPL = auto | native | python  (default: auto)

try:
    from ux_channel._cxb_native import encode as _native_encode  # type: ignore
    from ux_channel._cxb_native import decode as _native_decode  # type: ignore
except Exception:  # pragma: no cover
    _native_encode = None  # type: ignore
    _native_decode = None  # type: ignore


def native_available() -> bool:
    """True when the Rust (or other) ``_cxb_native`` extension is loaded."""
    return _native_encode is not None and _native_decode is not None


# Internal alias (same as native_available)
_native_available = native_available


def _cxb_impl_preference() -> str:
    """auto | native | python from env (invalid → auto)."""
    raw = (os.environ.get("UX_CHANNEL_CXB_IMPL") or "auto").strip().lower()
    if raw in ("auto", "native", "python", "rust", "py"):
        if raw == "rust":
            return "native"
        if raw == "py":
            return "python"
        return raw
    return "auto"


def cxb_impl() -> str:
    """Active CXB backend: ``"native"`` (Rust .so) or ``"python"``."""
    pref = _cxb_impl_preference()
    if pref == "python":
        return "python"
    if pref == "native":
        return "native" if native_available() else "python"
    # auto
    return "native" if native_available() else "python"


def encode_cxb_python(
    doc: Any, *, default: Optional[Callable[[Any], Any]] = None
) -> bytes:
    """Pure-Python CXB1 + CXBZ encoder (oracle / fallback).

    Always available — no Rust extension required. Prefer :func:`encode_cxb`
    which uses the Rust ``.so`` by default when present.
    """
    if default is None:
        default = str
    doc = _snapshot_for_cxb(doc)
    if not isinstance(doc, Mapping):
        # wrap generic
        doc = {"_": doc}

    # Frequency pass only when enough strings to benefit (avoids pure overhead)
    ops = doc.get("ops") if type(doc) is dict else None
    if isinstance(ops, list) and len(ops) >= INTERN_MIN_FREQ:
        allow = _allow_set_from_freq(_collect_string_freq(doc))
    elif type(doc) is dict and any(
        type(doc.get(k)) is str for k in ("action", "target", "request_id")
    ):
        allow = _allow_set_from_freq(_collect_string_freq(doc))
    else:
        allow = set()  # no intern — zero table tax
    enc = _Enc(default, allow=allow)
    # Body in a side buffer; string table written first from shared allow/table
    body = _Enc(default, allow=allow)

    if _is_intent(doc):
        kind = _KIND_INTENT
        pairs: list[tuple[int, Any, bool]] = []
        if "v" in doc:
            pairs.append((_I_V, doc["v"], True))
        if "action" in doc:
            pairs.append((_I_ACTION, doc["action"], True))
        if doc.get("args") is not None:
            pairs.append((_I_ARGS, doc["args"], False))
        if doc.get("cap") is not None:
            pairs.append((_I_CAP, doc["cap"], False))
        if doc.get("target") is not None:
            pairs.append((_I_TARGET, doc["target"], True))
        if doc.get("request_id") is not None:
            pairs.append((_I_REQUEST_ID, doc["request_id"], True))
        if doc.get("form") is not None:
            pairs.append((_I_FORM, doc["form"], False))
        if doc.get("accept_stream"):
            pairs.append((_I_ACCEPT_STREAM, True, False))
        if doc.get("idempotency_key") is not None:
            pairs.append((_I_IDEMPOTENCY, doc["idempotency_key"], True))
        if doc.get("meta") is not None:
            pairs.append((_I_META, doc["meta"], False))
        for tag, val, intern in pairs:
            body.w_field(tag, val, intern_str=intern)
        nfields = len(pairs)
        # extensions: keys not in intent schema
        ext = {k: v for k, v in doc.items() if k not in _INTENT_KEYS}
    elif _is_result(doc):
        kind = _KIND_RESULT
        pairs_r: list[tuple[int, Any]] = []
        if "v" in doc:
            pairs_r.append((_R_V, doc["v"]))
        if "ok" in doc:
            pairs_r.append((_R_OK, doc["ok"]))
        if "ops" in doc:
            pairs_r.append((_R_OPS, doc["ops"]))
        if doc.get("error") is not None:
            pairs_r.append((_R_ERROR, doc["error"]))
        if doc.get("meta") is not None:
            pairs_r.append((_R_META, doc["meta"]))
        nfields = len(pairs_r)
        for tag, val in pairs_r:
            if tag == _R_OPS and isinstance(val, (list, tuple)):
                body.buf.extend(struct.pack(">H", tag))
                _encode_ops(body, val)
            else:
                body.w_field(tag, val, intern_str=tag in (_R_V,))
        ext = {k: v for k, v in doc.items() if k not in _RESULT_KEYS}
    else:
        kind = _KIND_DOC
        # entire doc as extension map only
        nfields = 0
        ext = dict(doc)

    # Merge interning tables from body into enc
    enc.table = body.table
    enc.index = body.index

    out = bytearray()
    out += MAGIC
    out.append(kind & 0xFF)
    # string table
    enc.buf = out  # write table into out
    enc.write_table()
    # field count + fields
    out.extend(struct.pack(">H", nfields & 0xFFFF))
    out.extend(body.buf)
    # extensions
    _write_varint(out, len(ext))
    for k, v in ext.items():
        raw_k = str(k).encode("utf-8")
        _write_varint(out, len(raw_k))
        out.extend(raw_k)
        # value with wire prefix via temp enc sharing table
        tmp = _Enc(default, allow=allow)
        tmp.table = enc.table
        tmp.index = enc.index
        tmp.table_bytes = enc.table_bytes
        tmp.w_value(v)
        enc.table_bytes = tmp.table_bytes
        out.extend(tmp.buf)
    raw = bytes(out)
    import zlib as _zl
    crc = _zl.crc32(raw[4:]) & 0xFFFFFFFF
    raw = raw + b"~CRC" + struct.pack(">I", crc)

    if len(raw) >= CXBZ_MIN_PLAIN:
        comp = _zl.compress(raw, level=CXBZ_ZLIB_LEVEL)
        zlen = len(comp) + 4  # CXBZ magic
        saved = len(raw) - zlen
        if saved >= CXBZ_MIN_SAVE and (len(raw) / zlen) >= CXBZ_MIN_RATIO:
            return MAGIC_Z + comp
    return raw

def encode_cxb(doc: Any, *, default: Optional[Callable[[Any], Any]] = None) -> bytes:
    """Encode Intent/Result/dict → CXB1/CXBZ bytes.

    **Default:** Rust ``_cxb_native`` when the extension is installed.
    **Fallback:** :func:`encode_cxb_python` (full CXB1+CXBZ, always present).

    Safety: input is snapshotted before encode; native failures fall through
    to Python. Force backend with ``UX_CHANNEL_CXB_IMPL=python|native|auto``.
    """
    if default is None:
        default = str
    snap = _snapshot_for_cxb(doc)
    pref = _cxb_impl_preference()
    use_native = pref != "python" and _native_encode is not None and default is str
    if use_native:
        try:
            return _native_encode(snap)
        except Exception:
            pass  # never fail closed on accelerator bugs
    return encode_cxb_python(snap, default=default)


class _Dec:
    __slots__ = ("mv", "i", "table", "depth")

    def __init__(self, data: bytes):
        self.mv = memoryview(data)
        self.i = 0
        self.table: list[str] = []
        self.depth = 0

    def need(self, n: int) -> None:
        if self.i + n > len(self.mv):
            raise ValueError("truncated CXB")

    def u8(self) -> int:
        self.need(1)
        b = self.mv[self.i]
        self.i += 1
        return b

    def u16(self) -> int:
        self.need(2)
        v = struct.unpack_from(">H", self.mv, self.i)[0]
        self.i += 2
        return v

    def varint(self) -> int:
        n, self.i = _read_varint(self.mv, self.i)
        return n

    def read_table(self) -> None:
        n = self.varint()
        if n > MAX_STRING_TABLE:
            raise ValueError("CXB string table too large")
        self.table = []
        for _ in range(n):
            ln = self.varint()
            self.need(ln)
            s = bytes(self.mv[self.i : self.i + ln]).decode("utf-8")
            self.i += ln
            self.table.append(s)

    def value(self) -> Any:
        if self.depth > MAX_NEST_DEPTH:
            raise ValueError("CXB nesting too deep")
        self.depth += 1
        try:
            return self._value()
        finally:
            self.depth -= 1

    def _value(self) -> Any:
        w = self.u8()
        if w == _W_NULL:
            return None
        if w == _W_FALSE:
            return False
        if w == _W_TRUE:
            return True
        if w == _W_VARINT:
            return _zigzag_decode(self.varint())
        if w == _W_F64:
            self.need(8)
            v = struct.unpack_from(">d", self.mv, self.i)[0]
            self.i += 8
            return v
        if w == _W_UTF8:
            ln = self.varint()
            if ln > MAX_BLOB:
                raise ValueError("CXB string too large")
            self.need(ln)
            s = bytes(self.mv[self.i : self.i + ln]).decode("utf-8")
            self.i += ln
            return s
        if w == _W_BYTES:
            ln = self.varint()
            if ln > MAX_BLOB:
                raise ValueError("CXB bytes too large")
            self.need(ln)
            b = bytes(self.mv[self.i : self.i + ln])
            self.i += ln
            return b
        if w == _W_ARRAY:
            n = self.varint()
            if n > MAX_ARRAY_LEN:
                raise ValueError("CXB array too large")
            return [self.value() for _ in range(n)]
        if w == _W_MAP:
            n = self.varint()
            if n > MAX_ARRAY_LEN:
                raise ValueError("CXB map too large")
            out: dict[str, Any] = {}
            for _ in range(n):
                k = self.value()
                v = self.value()
                out[str(k)] = v
            return out
        if w == _W_FREE:
            ln = self.varint()
            if ln > MAX_BLOB:
                raise ValueError("CXB freeform too large")
            self.need(ln)
            blob = bytes(self.mv[self.i : self.i + ln])
            self.i += ln
            return _free_loads(blob)
        if w == _W_INTERN:
            idx = self.u16()
            if idx >= len(self.table):
                raise ValueError(f"intern index {idx} out of range")
            return self.table[idx]
        if w == _W_OPMAP:
            n = self.u8()
            out: dict[str, Any] = {}
            for _ in range(n):
                kt = self.u8()
                if kt == _OP_FREE_KEY:
                    ln = self.varint()
                    if ln > MAX_BLOB:
                        raise ValueError("op free-key too large")
                    self.need(ln)
                    key = bytes(self.mv[self.i : self.i + ln]).decode("utf-8")
                    self.i += ln
                else:
                    key = _OP_TAG_KEYS.get(kt)
                    if key is None:
                        key = f"ext:{kt}"
                out[key] = self.value()
            return out
        raise ValueError(f"unknown CXB wire type {w}")


def is_cxb(data: bytes) -> bool:
    """True if buffer starts with CXB1 or CXBZ."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 4:
        return False
    m = bytes(data[:4])
    return m == MAGIC or m == MAGIC_Z


def decode_cxb_python(data: bytes) -> Any:
    """Pure-Python CXB1 + CXBZ decoder (oracle / fallback).

    Always available — no Rust extension required.
    """
    data = bytes(data)  # freeze shared buffers
    if not is_cxb(data):
        raise ValueError("not CXB (bad magic)")
    if data[:4] == MAGIC_Z:
        import zlib
        if len(data) > MAX_BLOB:
            raise ValueError("CXBZ frame too large")
        try:
            data = zlib.decompress(data[4:], max_length=MAX_BLOB)
        except TypeError:
            data = zlib.decompress(data[4:])
            if len(data) > MAX_BLOB:
                raise ValueError("CXBZ expand exceeds limit")
        except zlib.error as exc:
            raise ValueError(f"CXBZ decompress failed: {exc}") from exc
        if len(data) > MAX_BLOB:
            raise ValueError("CXBZ expand exceeds limit")
        if data[:4] != MAGIC:
            raise ValueError("CXBZ payload not CXB1")

    if len(data) >= 12 and data[-8:-4] == b"~CRC" and data[:4] == MAGIC:
        import zlib as _zl

        body, stored = data[:-8], struct.unpack(">I", data[-4:])[0]
        calc = _zl.crc32(body[4:]) & 0xFFFFFFFF
        if stored != calc:
            raise ValueError("CXB CRC mismatch (frame corrupted)")
        data = body

    d = _Dec(data)
    d.i = 4  # skip magic

    kind = d.u8()
    d.read_table()
    nfields = d.u16()
    if nfields > MAX_FIELDS:
        raise ValueError("CXB field count too large")
    doc: dict[str, Any] = {}

    if kind == _KIND_INTENT:
        tag_map = {
            _I_V: "v",
            _I_ACTION: "action",
            _I_ARGS: "args",
            _I_CAP: "cap",
            _I_TARGET: "target",
            _I_REQUEST_ID: "request_id",
            _I_FORM: "form",
            _I_ACCEPT_STREAM: "accept_stream",
            _I_IDEMPOTENCY: "idempotency_key",
            _I_META: "meta",
        }
        for _ in range(nfields):
            tag = d.u16()
            val = d.value()
            key = tag_map.get(tag)
            if key is not None:
                doc[key] = val
    elif kind == _KIND_RESULT:
        tag_map = {
            _R_V: "v",
            _R_OK: "ok",
            _R_OPS: "ops",
            _R_ERROR: "error",
            _R_META: "meta",
        }
        for _ in range(nfields):
            tag = d.u16()
            val = d.value()
            key = tag_map.get(tag)
            if key is not None:
                doc[key] = val
    elif kind == _KIND_DOC:
        if nfields != 0:
            # unexpected; skip by reading nfields values if any were written
            for _ in range(nfields):
                d.u16()
                d.value()
    else:
        raise ValueError(f"unknown CXB kind {kind}")

    # extensions
    n_ext = d.varint()
    for _ in range(n_ext):
        ln = d.varint()
        d.need(ln)
        k = bytes(d.mv[d.i : d.i + ln]).decode("utf-8")
        d.i += ln
        doc[k] = d.value()

    return doc


def decode_cxb(data: bytes) -> Any:
    """Decode CXB1/CXBZ → dict.

    **Default:** Rust ``_cxb_native`` when available; else pure Python.
    Force with ``UX_CHANNEL_CXB_IMPL=python|native|auto``.
    """
    data = bytes(data)
    if not is_cxb(data):
        raise ValueError("not CXB (bad magic)")
    if _cxb_impl_preference() != "python" and _native_decode is not None:
        try:
            return _native_decode(data)
        except Exception:
            pass
    return decode_cxb_python(data)


def make_cxb_codec():
    """Internal factory for the wire plugin registry (apps use encode/decode).

    Engine label: ``cxb-native`` when Rust ``.so`` is default-active, else ``cxb``.
    """
    from ux_channel.wire.core import Codec

    def _dumps(obj: Any, *, pretty: bool, default: Any) -> bytes:
        return encode_cxb(obj, default=default or str)

    def _loads(data: Any) -> Any:
        if isinstance(data, str):
            data = data.encode("latin-1")
        return decode_cxb(bytes(data))

    eng = "cxb-native" if cxb_impl() == "native" else "cxb"
    return Codec(
        format="cxb",
        engine=eng,
        media_type=MEDIA_TYPE,
        produces_bytes=True,
        _dumps=_dumps,
        _loads=_loads,
    )
