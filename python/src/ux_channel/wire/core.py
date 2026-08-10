# Copyright (c) 2026 UX-CHANNEL
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
"""Core wire codec: formats, JSON engines, process policy.

Production contract
* **Safe floor:** process always has a working JSON codec (stdlib at minimum).
* **Default format is JSON** — binary (msgpack/cbor/cxb) is opt-in only.
* **Immutable codecs** shared across threads; encode/decode use per-call buffers.
* **Policy swap is atomic** — a failed ``configure_wire`` never leaves a broken…"""

from __future__ import annotations

import json as _stdlib_json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence, Union

__all__ = [
    "MEDIA_TYPES",
    "Codec",
    "WireFormatPlugin",
    "WireBlob",
    "WirePolicy",
    "available_engines",
    "available_formats",
    "configure_wire",
    "list_wire_plugins",
    "register_wire_format",
    "unregister_wire_format",
    "decode",
    "dumps",
    "dumps_bytes",
    "encode",
    "encode_many",
    "get_codec",
    "get_policy",
    "loads",
    "loads_bytes",
    "reset_wire",
    "size_of",
    "try_decode",
    "decode_complete",
    "clear_codec_cache",
]

Raw = Union[str, bytes, bytearray]

# Media types — updated when wire format plugins register/replace
MEDIA_TYPES: dict[str, str] = {
    "json": "application/ux-channel+json",
}

# Content-Type / Accept → format name
_MEDIA_ALIASES: dict[str, str] = {
    "application/json": "json",
    "application/ux-channel+json": "json",
}


def _default(obj: Any) -> Any:
    """Fail-soft for non-JSON-native types."""
    return str(obj)


@dataclass(frozen=True)
class Codec:
    """Immutable encoder/decoder for one format (+ engine name)."""

    format: str  # json | msgpack | cbor
    engine: str  # orjson | ujson | stdlib | msgpack | cbor2
    media_type: str
    produces_bytes: bool
    _dumps: Callable[..., Any]
    _loads: Callable[..., Any]

    @property
    def name(self) -> str:
        return self.engine if self.format == "json" else self.format

    def dumps(
        self,
        obj: Any,
        *,
        pretty: bool = False,
        default: Any = _default,
        indent: Any = None,
        **_ignored: Any,
    ) -> str:
        """Encode to **text**. Binary formats return base-incompatible data —
        only valid for JSON formats; raises for binary."""
        if self.format != "json":
            raise TypeError(
                f"dumps() is JSON-only; active format={self.format!r}. "
                "Use encode() for binary wire formats."
            )
        if indent not in (None, 0, False):
            pretty = True
        raw = self.dumps_bytes(obj, pretty=pretty, default=default)
        return raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)

    def dumps_bytes(
        self,
        obj: Any,
        *,
        pretty: bool = False,
        default: Any = _default,
        indent: Any = None,
        **_ignored: Any,
    ) -> bytes:
        if indent not in (None, 0, False):
            pretty = True
        out = self._dumps(obj, pretty=pretty, default=default)
        if isinstance(out, (bytes, bytearray)):
            return bytes(out)
        return str(out).encode("utf-8")

    def loads(self, data: Raw) -> Any:
        if isinstance(data, (bytes, bytearray)):
            return self._loads(bytes(data))
        if self.format != "json":
            raise TypeError(
                f"loads(str) is JSON-only; active format={self.format!r}. "
                "Pass bytes or use decode()."
            )
        return self._loads(data)

    def loads_bytes(self, data: bytes) -> Any:
        return self._loads(data)


@dataclass(frozen=True)
class WireBlob:
    """Encoded document + media type (ready for HTTP body)."""

    data: bytes
    media_type: str
    format: str
    engine: str
    fallback: bool = False
    preferred_format: str | None = None


@dataclass(frozen=True)
class WirePolicy:
    """Process-level format + engine selection."""

    format: str  # json | msgpack | cbor
    engine: str  # auto | orjson | ujson | stdlib (JSON only)
    codec: Codec

    def media_type(self) -> str:
        return self.codec.media_type


# JSON engines


def _make_stdlib_json() -> Codec:
    def _dumps(obj: Any, *, pretty: bool, default: Any) -> str:
        if pretty:
            return _stdlib_json.dumps(obj, indent=2, default=default, ensure_ascii=False)
        return _stdlib_json.dumps(
            obj, separators=(",", ":"), default=default, ensure_ascii=False
        )

    def _loads(data: Raw) -> Any:
        if isinstance(data, (bytes, bytearray)):
            return _stdlib_json.loads(data.decode("utf-8"))
        return _stdlib_json.loads(data)

    return Codec(
        format="json",
        engine="stdlib",
        media_type=MEDIA_TYPES["json"],
        produces_bytes=False,
        _dumps=_dumps,
        _loads=_loads,
    )


def _make_orjson() -> Optional[Codec]:
    try:
        import orjson  # type: ignore
    except ImportError:
        return None

    def _dumps(obj: Any, *, pretty: bool, default: Any) -> bytes:
        opt = orjson.OPT_NON_STR_KEYS
        if pretty:
            opt |= orjson.OPT_INDENT_2

        def _d(o: Any) -> Any:
            if default is None:
                raise TypeError(type(o))
            return default(o)

        return orjson.dumps(obj, default=_d, option=opt)

    def _loads(data: Raw) -> Any:
        return orjson.loads(data)

    return Codec(
        format="json",
        engine="orjson",
        media_type=MEDIA_TYPES["json"],
        produces_bytes=True,
        _dumps=_dumps,
        _loads=_loads,
    )


def _make_ujson() -> Optional[Codec]:
    try:
        import ujson  # type: ignore
    except ImportError:
        return None

    def _dumps(obj: Any, *, pretty: bool, default: Any) -> str:
        try:
            if pretty:
                return ujson.dumps(obj, indent=2, ensure_ascii=False, default=default)
            return ujson.dumps(
                obj, ensure_ascii=False, escape_forward_slashes=False, default=default
            )
        except TypeError:
            text = _stdlib_json.dumps(
                obj,
                separators=None if pretty else (",", ":"),
                indent=2 if pretty else None,
                default=default,
                ensure_ascii=False,
            )
            if pretty:
                return text
            try:
                return ujson.dumps(
                    ujson.loads(text), ensure_ascii=False, escape_forward_slashes=False
                )
            except Exception:
                return text

    def _loads(data: Raw) -> Any:
        if isinstance(data, (bytes, bytearray)):
            return ujson.loads(data.decode("utf-8"))
        return ujson.loads(data)

    return Codec(
        format="json",
        engine="ujson",
        media_type=MEDIA_TYPES["json"],
        produces_bytes=False,
        _dumps=_dumps,
        _loads=_loads,
    )


# Binary formats (opt-in upgrades)


def _make_msgpack() -> Optional[Codec]:
    try:
        import msgpack  # type: ignore
    except ImportError:
        return None

    def _dumps(obj: Any, *, pretty: bool, default: Any) -> bytes:
        # pretty ignored (binary)
        def _d(o: Any) -> Any:
            if default is None:
                raise TypeError(type(o))
            return default(o)

        return msgpack.packb(obj, default=_d, use_bin_type=True)

    def _loads(data: Raw) -> Any:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return msgpack.unpackb(bytes(data), raw=False, strict_map_key=False)

    return Codec(
        format="msgpack",
        engine="msgpack",
        media_type=MEDIA_TYPES["msgpack"],
        produces_bytes=True,
        _dumps=_dumps,
        _loads=_loads,
    )


def _make_cbor() -> Optional[Codec]:
    try:
        import cbor2  # type: ignore
    except ImportError:
        return None

    def _dumps(obj: Any, *, pretty: bool, default: Any) -> bytes:
        def _d(encoder: Any, o: Any) -> None:  # cbor2 default hook shape varies
            encoder.encode(default(o) if default else str(o))

        try:
            return cbor2.dumps(obj, default=default)
        except TypeError:
            # older/newer API differences — fall through with str map via json bridge
            import json as _j

            return cbor2.dumps(_j.loads(_j.dumps(obj, default=default)))

    def _loads(data: Raw) -> Any:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return cbor2.loads(bytes(data))

    return Codec(
        format="cbor",
        engine="cbor2",
        media_type=MEDIA_TYPES["cbor"],
        produces_bytes=True,
        _dumps=_dumps,
        _loads=_loads,
    )


# Discovery + build


# Wire format plugins (CXB is one plugin — replaceable anytime)


@dataclass(frozen=True)
class WireFormatPlugin:
    """Registered binary/text wire format (json is core, not a plugin)."""

    name: str
    media_type: str
    factory: Callable[[], "Codec"]
    available: Callable[[], bool]
    sniff: Optional[Callable[[bytes], bool]] = None
    media_aliases: tuple[str, ...] = ()
    core: bool = False


_PLUGINS: dict[str, WireFormatPlugin] = {}


def list_wire_plugins() -> list[str]:
    """Registered format plugin names (including unavailable optionals)."""
    with _LOCK:
        return sorted(_PLUGINS.keys())


def register_wire_format(
    name: str,
    *,
    media_type: str,
    factory: Callable[[], "Codec"],
    available: Optional[Callable[[], bool]] = None,
    sniff: Optional[Callable[[bytes], bool]] = None,
    media_aliases: Sequence[str] = (),
    replace: bool = False,
    core: bool = False,
) -> None:
    """Register or replace a format plugin (e.g. swap CXB). Cache cleared."""
    key = (name or "").strip().lower()
    if not key or key == "json":
        raise ValueError("register_wire_format: use a non-empty name other than 'json'")
    if not callable(factory):
        raise TypeError("factory must be callable")
    if not (media_type or "").strip():
        raise ValueError("media_type is required")
    avail = available if available is not None else (lambda: True)
    mt = media_type.strip()

    def _wrapped_factory() -> Codec:
        c = factory()
        if not isinstance(c, Codec):
            raise TypeError(f"wire plugin {key!r} factory must return Codec")
        if not callable(getattr(c, "_dumps", None)) or not callable(
            getattr(c, "_loads", None)
        ):
            raise TypeError(f"wire plugin {key!r} Codec missing dumps/loads")
        # Normalize identity to the registered name/media
        if c.format != key or c.media_type != mt:
            c = Codec(
                format=key,
                engine=c.engine or key,
                media_type=mt,
                produces_bytes=bool(c.produces_bytes),
                _dumps=c._dumps,
                _loads=c._loads,
            )
        return c

    with _LOCK:
        if key in _PLUGINS and not replace:
            raise ValueError(
                f"wire format {key!r} already registered — pass replace=True to swap"
            )
        prev = _PLUGINS.get(key)
        if prev is not None and prev.core and not core:
            raise ValueError(f"cannot replace core plugin {key!r}")
        plug = WireFormatPlugin(
            name=key,
            media_type=mt,
            factory=_wrapped_factory,
            available=avail,
            sniff=sniff,
            media_aliases=tuple(a.strip() for a in media_aliases if a and str(a).strip()),
            core=core,
        )
        _PLUGINS[key] = plug
        MEDIA_TYPES[key] = mt
        _MEDIA_ALIASES[mt.lower()] = key
        for a in plug.media_aliases:
            _MEDIA_ALIASES[a.lower()] = key
        dead = [k for k in _CODEC_CACHE if k[0] == key]
        for k in dead:
            del _CODEC_CACHE[k]
    # If process policy pointed at this format, rebuild so new factory is live
    try:
        pol = get_policy()
        if pol.format == key:
            _set_policy(key, pol.engine)
    except Exception:
        pass


def unregister_wire_format(name: str) -> None:
    """Remove a non-core plugin (e.g. disable CXB in a constrained deploy)."""
    key = (name or "").strip().lower()
    if key == "json":
        raise ValueError("cannot unregister core format 'json'")
    with _LOCK:
        plug = _PLUGINS.get(key)
        if plug is None:
            return
        if plug.core:
            raise ValueError(f"cannot unregister core format {key!r}")
        del _PLUGINS[key]
        MEDIA_TYPES.pop(key, None)
        # prune aliases pointing at this format
        for a, fmt in list(_MEDIA_ALIASES.items()):
            if fmt == key:
                del _MEDIA_ALIASES[a]
        dead = [k for k in _CODEC_CACHE if k[0] == key]
        for k in dead:
            del _CODEC_CACHE[k]
    try:
        pol = get_policy()
        if pol.format == key:
            _set_policy("json", "auto")
    except Exception:
        pass


def _plugin(name: str) -> Optional[WireFormatPlugin]:
    with _LOCK:
        return _PLUGINS.get(name)


def _register_builtin_plugins() -> None:
    """Install default plugins once. CXB is a plugin, not a hard-wired branch."""

    def _msgpack_avail() -> bool:
        return _make_msgpack() is not None

    def _cbor_avail() -> bool:
        return _make_cbor() is not None

    def _msgpack_factory() -> Codec:
        c = _make_msgpack()
        if c is None:
            raise RuntimeError("msgpack not installed")
        return c

    def _cbor_factory() -> Codec:
        c = _make_cbor()
        if c is None:
            raise RuntimeError("cbor2 not installed")
        return c

    def _cxb_factory() -> Codec:
        from ux_channel.wire.cxb import make_cxb_codec

        return make_cxb_codec()

    def _cxb_sniff(data: bytes) -> bool:
        from ux_channel.wire.cxb import is_cxb

        return is_cxb(data)

    # Direct insert (avoid replace rules during bootstrap)
    builtins = [
        WireFormatPlugin(
            name="msgpack",
            media_type="application/ux-channel+msgpack",
            factory=_msgpack_factory,
            available=_msgpack_avail,
            media_aliases=("application/msgpack", "application/x-msgpack"),
        ),
        WireFormatPlugin(
            name="cbor",
            media_type="application/ux-channel+cbor",
            factory=_cbor_factory,
            available=_cbor_avail,
            media_aliases=("application/cbor",),
        ),
        WireFormatPlugin(
            name="cxb",
            media_type="application/ux-channel+cxb",
            factory=_cxb_factory,
            available=lambda: True,
            sniff=_cxb_sniff,
            media_aliases=("application/cxb",),
        ),
    ]
    with _LOCK:
        for plug in builtins:
            _PLUGINS[plug.name] = plug
            MEDIA_TYPES[plug.name] = plug.media_type
            _MEDIA_ALIASES[plug.media_type.lower()] = plug.name
            for a in plug.media_aliases:
                _MEDIA_ALIASES[a.lower()] = plug.name


def available_engines() -> list[str]:
    """Installed JSON engines, preferred first."""
    names: list[str] = []
    if _make_orjson() is not None:
        names.append("orjson")
    if _make_ujson() is not None:
        names.append("ujson")
    names.append("stdlib")
    return names


def available_formats() -> list[str]:
    """Wire formats constructible in this process (plugins + json)."""
    out = ["json"]
    with _LOCK:
        plugs = list(_PLUGINS.values())
    for plug in plugs:
        try:
            if plug.available():
                out.append(plug.name)
        except Exception:
            continue
    return out


def _build_json_engine(engine: str) -> Codec:
    key = (engine or "auto").strip().lower() or "auto"
    if key == "auto":
        for factory in (_make_orjson, _make_ujson, _make_stdlib_json):
            c = factory()
            if c is not None:
                return c
        return _make_stdlib_json()
    if key == "stdlib":
        return _make_stdlib_json()
    if key == "orjson":
        c = _make_orjson()
        if c is None:
            raise RuntimeError("orjson is not installed")
        return c
    if key == "ujson":
        c = _make_ujson()
        if c is None:
            raise RuntimeError("ujson is not installed")
        return c
    raise ValueError(f"unknown JSON engine: {engine!r}")


def _env_format() -> str:
    return (os.environ.get("UX_CHANNEL_WIRE") or "json").strip().lower() or "json"


def _env_engine() -> str:
    return (os.environ.get("UX_CHANNEL_WIRE_ENGINE") or "auto").strip().lower() or "auto"


_LOCK = threading.RLock()
_POLICY: WirePolicy
_CODEC_CACHE: dict[tuple[str, str], Codec] = {}
# Batch workers: 0 = sequential.
_BATCH_WORKERS = 0
_MAX_BATCH_WORKERS = 32


def _parse_workers_env() -> int:
    raw = (os.environ.get("UX_CHANNEL_WIRE_WORKERS") or "0").strip() or "0"
    try:
        n = int(raw)
    except ValueError:
        return 0
    return max(0, min(n, _MAX_BATCH_WORKERS))


_BATCH_WORKERS = _parse_workers_env()


def _safe_json_codec() -> Codec:
    return _make_stdlib_json()


def _resolve_json_engine_name(engine: str) -> str:
    key = (engine or "auto").strip().lower() or "auto"
    if key == "auto":
        return available_engines()[0]
    if key == "stdlib":
        return "stdlib"
    if key in ("orjson", "ujson"):
        if key in available_engines():
            return key
        return available_engines()[0]
    raise ValueError(f"unknown JSON engine: {engine!r} (auto|orjson|ujson|stdlib)")


def _resolve_format_name(fmt: str) -> str:
    key = (fmt or "json").strip().lower() or "json"
    if key == "json":
        return "json"
    with _LOCK:
        if key in _PLUGINS:
            return key
    raise ValueError(
        f"unknown wire format: {fmt!r}. "
        f"Choose from {available_formats()}."
    )


def _format_available(fmt: str) -> bool:
    return fmt in available_formats()


def _cached_codec(fmt: str, engine: str = "auto") -> Codec:
    try:
        fmt_n = _resolve_format_name(fmt)
    except ValueError:
        fmt_n = "json"
    if fmt_n == "json":
        try:
            eng_n = _resolve_json_engine_name(engine)
        except ValueError:
            eng_n = "stdlib"
    else:
        eng_n = fmt_n  # binary engines are the format name
        if not _format_available(fmt_n):
            fmt_n, eng_n = "json", _resolve_json_engine_name("auto")

    key = (fmt_n, eng_n)
    with _LOCK:
        hit = _CODEC_CACHE.get(key)
        if hit is not None:
            return hit

    try:
        if fmt_n == "json":
            codec = _build_json_engine(eng_n)
        else:
            plug = _plugin(fmt_n)
            if plug is None or not plug.available():
                codec = _safe_json_codec()
                key = (codec.format, codec.engine)
            else:
                codec = plug.factory()
    except Exception:
        codec = _safe_json_codec()
        key = (codec.format, codec.engine)

    with _LOCK:
        return _CODEC_CACHE.setdefault(key, codec)


def _set_policy(fmt: str, engine: str) -> WirePolicy:
    global _POLICY
    try:
        codec = _cached_codec(fmt, engine)
    except Exception:
        codec = _safe_json_codec()
    pol = WirePolicy(format=codec.format, engine=codec.engine, codec=codec)
    with _LOCK:
        _POLICY = pol
        return _POLICY


def _init_policy() -> None:
    fmt = _env_format()
    eng = _env_engine()
    try:
        fmt_n = _resolve_format_name(fmt)
    except ValueError:
        fmt_n = "json"
    if not _format_available(fmt_n):
        fmt_n = "json"
    try:
        _set_policy(fmt_n, eng)
    except Exception:
        _set_policy("json", "stdlib")


_register_builtin_plugins()
_init_policy()


def get_policy() -> WirePolicy:
    """Current policy snapshot."""
    with _LOCK:
        return _POLICY


def get_codec() -> Codec:
    """Active codec."""
    return get_policy().codec


def set_batch_workers(n: int) -> int:
    """Batch worker default (0=sequential, max 32)."""
    global _BATCH_WORKERS
    try:
        v = int(n)
    except (TypeError, ValueError):
        v = 0
    with _LOCK:
        _BATCH_WORKERS = max(0, min(v, _MAX_BATCH_WORKERS))
        return _BATCH_WORKERS


def get_batch_workers() -> int:
    with _LOCK:
        return _BATCH_WORKERS


def clear_codec_cache() -> None:
    """Drop codec cache (tests)."""
    with _LOCK:
        _CODEC_CACHE.clear()


def configure_wire(
    format: str | None = None,
    engine: str | None = None,
    *,
    strict: bool = False,
) -> Codec:
    """Set process format and/or JSON engine.

    format: json | msgpack | cbor | cxb
    engine: auto | orjson | ujson | stdlib
    strict: raise on unknown/missing (default soft → JSON floor)
    """
    _engines = {"auto", "orjson", "ujson", "stdlib"}
    known = set(available_formats()) | set(list_wire_plugins()) | {"json"}

    cur = get_policy()
    fmt = format
    eng = engine

    if fmt is None and eng is not None:
        fmt = "json"  # engine-only always targets JSON
    if fmt is None:
        fmt = cur.format
    if eng is None:
        eng = cur.engine if cur.format == "json" else "auto"

    fmt_l = str(fmt).strip().lower()
    eng_l = str(eng).strip().lower() if eng is not None else "auto"

    if fmt_l not in known and fmt_l != "json":
        if strict:
            raise ValueError(
                f"unknown wire format: {fmt!r}. Choose from {sorted(known)}."
            )
        fmt_l = "json"

    if eng_l not in _engines:
        if strict:
            raise ValueError(f"unknown JSON engine: {eng!r}. Choose from {sorted(_engines)}.")
        eng_l = "auto"

    if fmt_l != "json" and not _format_available(fmt_l):
        if strict:
            raise RuntimeError(
                f"wire format {fmt_l!r} unavailable. formats={available_formats()}"
            )
        fmt_l = "json"

    if fmt_l == "json" and strict and eng_l in ("orjson", "ujson"):
        if eng_l not in available_engines():
            raise RuntimeError(f"{eng_l} is not installed")

    prev = get_policy()
    try:
        return _set_policy(fmt_l, eng_l).codec
    except Exception:
        try:
            _set_policy(prev.format, prev.engine)
        except Exception:
            _set_policy("json", "stdlib")
        if strict:
            raise
        return get_codec()


def reset_wire() -> Codec:
    """Reload policy from env."""
    clear_codec_cache()
    _init_policy()
    return get_codec()


def _snapshot_doc(obj: Any) -> Any:
    """Shallow snapshot so concurrent mutation cannot tear encode."""
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(v, Mapping):
                out[str(k)] = dict(v)
            elif isinstance(v, list):
                out[str(k)] = [
                    dict(x) if isinstance(x, Mapping) else x for x in v
                ]
            elif isinstance(v, tuple):
                out[str(k)] = tuple(
                    dict(x) if isinstance(x, Mapping) else x for x in v
                )
            else:
                out[str(k)] = v
        return out
    if isinstance(obj, list):
        return [dict(x) if isinstance(x, Mapping) else x for x in obj]
    return obj


def _encode_one(
    obj: Any,
    codec: Codec,
    *,
    pretty: bool,
    default: Any,
) -> bytes:
    return codec.dumps_bytes(obj, pretty=pretty, default=default)


def encode(
    obj: Any,
    *,
    format: str | None = None,
    engine: str | None = None,
    pretty: bool = False,
    default: Any = _default,
    complete: bool = True,
) -> WireBlob:
    """Encode document → WireBlob. complete=True falls back through formats → JSON."""
    preferred: str
    if format is None and engine is None:
        codec = get_codec()
        preferred = codec.format
    else:
        preferred = (format or get_policy().format or "json")
        codec = _cached_codec(preferred, engine or "auto")
        preferred = codec.format

    snap = _snapshot_doc(obj)
    chain: list[str] = [preferred]
    if complete:
        for alt in ("cxb", "msgpack", "json"):
            if alt not in chain and alt in available_formats():
                chain.append(alt)
        if "json" not in chain:
            chain.append("json")

    last_err: Exception | None = None
    for i, fmt in enumerate(chain):
        c = _cached_codec(fmt, engine or "auto")
        try:
            data = _encode_one(snap, c, pretty=pretty, default=default)
            return WireBlob(
                data=data,
                media_type=c.media_type,
                format=c.format,
                engine=c.engine,
                fallback=(c.format != preferred),
                preferred_format=preferred if c.format != preferred else None,
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if not complete:
                break
            continue

    # Absolute floor
    c = _safe_json_codec()
    try:
        data = _encode_one(snap, c, pretty=pretty, default=default)
        return WireBlob(
            data=data,
            media_type=c.media_type,
            format=c.format,
            engine=c.engine,
            fallback=True,
            preferred_format=preferred,
        )
    except Exception as exc:
        raise ValueError(
            f"wire encode failed (preferred={preferred!r}): {last_err or exc}"
        ) from exc


def _decode_one(data: Raw, fmt: str, engine: str | None) -> Any:
    codec = _cached_codec(fmt, engine or "auto")
    try:
        return codec.loads(data)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"wire decode failed ({codec.format}): {exc}") from exc


def _sniff_format(data: Raw) -> str | None:
    """Probe plugins (CXB magic etc.), then weak JSON/msgpack hints."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 1:
        return None
    raw = bytes(data)
    with _LOCK:
        plugs = list(_PLUGINS.values())
    for plug in plugs:
        if plug.sniff is None:
            continue
        try:
            if plug.sniff(raw):
                return plug.name
        except Exception:
            continue
    if raw[:1] in (b"{", b"["):
        return "json"
    # weak msgpack map/array fixmap heuristics
    b0 = raw[0]
    if b0 in (
        0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
        0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F,
        0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97,
        0xDE, 0xDF, 0xDC, 0xDD,
    ):
        if "msgpack" in available_formats():
            return "msgpack"
    return None


def decode(

    data: Raw,
    *,
    format: str | None = None,
    media_type: str | None = None,
    engine: str | None = None,
    complete: bool = True,
) -> Any:
    """Decode wire bytes/text.

    Thread-safe. Empty → ``{}``.

    ``complete=True`` (default): if the preferred format fails, try magic
    sniff + remaining formats so a mislabeled or partially corrupted frame
    can still yield the document and **complete the intended action**.
    """
    if data is None or data == b"" or data == "":
        return {}
    if isinstance(data, bytearray):
        data = bytes(data)

    preferred: str | None = format
    if preferred is None and media_type:
        mt = str(media_type).split(";")[0].strip().lower()
        preferred = _MEDIA_ALIASES.get(mt)
    if preferred is None:
        preferred = _sniff_format(data) or get_codec().format

    chain: list[str] = [preferred]
    if complete:
        sniffed = _sniff_format(data)
        if sniffed and sniffed not in chain:
            chain.append(sniffed)
        for alt in ("json", "cxb", "msgpack"):
            if alt not in chain and (alt == "json" or alt in available_formats()):
                chain.append(alt)

    last_err: Exception | None = None
    for fmt in chain:
        try:
            return _decode_one(data, fmt, engine)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if not complete:
                break
            continue
    raise ValueError(
        f"wire decode failed (tried={chain}): {last_err}"
    ) from last_err


def try_decode(
    data: Raw,
    *,
    format: str | None = None,
    media_type: str | None = None,
    engine: str | None = None,
    default: Any = None,
    complete: bool = True,
) -> Any:
    """Like ``decode`` but returns ``default`` on failure (never raises)."""
    try:
        return decode(
            data,
            format=format,
            media_type=media_type,
            engine=engine,
            complete=complete,
        )
    except Exception:
        return default


def decode_complete(
    data: Raw,
    *,
    format: str | None = None,
    media_type: str | None = None,
) -> tuple[Any, str]:
    """Decode and report which format succeeded — for hosts/diagnostics."""
    if data is None or data == b"" or data == "":
        return {}, "empty"
    if isinstance(data, bytearray):
        data = bytes(data)
    preferred = format
    if preferred is None and media_type:
        preferred = _MEDIA_ALIASES.get(str(media_type).split(";")[0].strip().lower())
    if preferred is None:
        preferred = _sniff_format(data) or "json"
    chain = [preferred]
    for alt in (_sniff_format(data), "json", "cxb", "msgpack"):
        if alt and alt not in chain:
            chain.append(alt)
    for fmt in chain:
        try:
            return _decode_one(data, fmt, None), fmt
        except Exception:
            continue
    raise ValueError(f"wire decode_complete failed (tried={chain})")


def encode_many(
    docs: Sequence[Any],
    *,
    format: str | None = None,
    engine: str | None = None,
    workers: int | None = None,
    pretty: bool = False,
) -> list[WireBlob]:
    """Encode many documents. Default sequential; opt-in thread pool.

    * ``workers is None`` → process default (0 sequential)
    * ``workers`` clamped to 0..32
    * On worker failure the exception propagates; no partial silent list
    """
    try:
        items = list(docs)
    except TypeError:
        items = [docs]
    if not items:
        return []
    if workers is None:
        n = get_batch_workers()
    else:
        try:
            n = int(workers)
        except (TypeError, ValueError):
            n = 0
    n = max(0, min(n, _MAX_BATCH_WORKERS))
    if n <= 1 or len(items) == 1:
        return [encode(d, format=format, engine=engine, pretty=pretty) for d in items]

    out: list[Optional[WireBlob]] = [None] * len(items)

    def _one(i: int, d: Any) -> tuple[int, WireBlob]:
        return i, encode(d, format=format, engine=engine, pretty=pretty)

    with ThreadPoolExecutor(max_workers=min(n, len(items))) as pool:
        futs = [pool.submit(_one, i, d) for i, d in enumerate(items)]
        for fut in as_completed(futs):
            i, blob = fut.result()
            out[i] = blob
    # If any slot missing, something went wrong
    if any(b is None for b in out):
        raise RuntimeError("encode_many: incomplete results")
    return out  # type: ignore[return-value]


def decode_many(
    payloads: Sequence[Raw],
    *,
    format: str | None = None,
    media_type: str | None = None,
    engine: str | None = None,
    workers: int | None = None,
) -> list[Any]:
    """Decode many payloads (same concurrency rules as ``encode_many``)."""
    try:
        items = list(payloads)
    except TypeError:
        items = [payloads]
    if not items:
        return []
    if workers is None:
        n = get_batch_workers()
    else:
        try:
            n = int(workers)
        except (TypeError, ValueError):
            n = 0
    n = max(0, min(n, _MAX_BATCH_WORKERS))
    if n <= 1 or len(items) == 1:
        return [
            decode(p, format=format, media_type=media_type, engine=engine)
            for p in items
        ]
    out: list[Any] = [None] * len(items)

    def _one(i: int, p: Raw) -> tuple[int, Any]:
        return i, decode(p, format=format, media_type=media_type, engine=engine)

    with ThreadPoolExecutor(max_workers=min(n, len(items))) as pool:
        futs = [pool.submit(_one, i, p) for i, p in enumerate(items)]
        for fut in as_completed(futs):
            i, doc = fut.result()
            out[i] = doc
    return out


def _json_codec() -> Codec:
    """JSON engine for dumps/loads — never msgpack/cbor/cxb."""
    pol = get_policy()
    if pol.format == "json":
        return pol.codec
    return _cached_codec("json", "auto")


def dumps(
    obj: Any,
    *,
    pretty: bool = False,
    default: Any = _default,
    indent: Any = None,
    **ignored: Any,
) -> str:
    """JSON string (best engine). Independent of binary wire format opt-in."""
    return _json_codec().dumps(
        obj, pretty=pretty, default=default, indent=indent, **ignored
    )


def dumps_bytes(
    obj: Any,
    *,
    pretty: bool = False,
    default: Any = _default,
    indent: Any = None,
    **ignored: Any,
) -> bytes:
    return _json_codec().dumps_bytes(
        obj, pretty=pretty, default=default, indent=indent, **ignored
    )


def loads(data: Raw) -> Any:
    """Decode JSON text/bytes (best engine)."""
    return _json_codec().loads(data)


def loads_bytes(data: bytes) -> Any:
    return _json_codec().loads_bytes(data)


def size_of(obj: Any) -> int:
    """Byte size of compact **JSON** encoding (limits / guest budgets)."""
    return len(dumps_bytes(obj))


def format_from_media_type(media_type: str | None) -> Optional[str]:
    if not media_type:
        return None
    mt = media_type.split(";")[0].strip().lower()
    return _MEDIA_ALIASES.get(mt)
