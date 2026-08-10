#!/usr/bin/env python3
# Copyright (c) 2026 UX-CHANNEL
"""
In-process mutational fuzzer for the wire codec (AFL / libFuzzer style).

Why not ship AFL/libFuzzer binaries here?
-----------------------------------------
ux-channel's codecs are **Python** (orjson/msgpack C under the hood). Full
AFL++/libFuzzer shines on C/C++ with coverage instrumentation. For this
library we provide:

1. **This harness** — seed corpus + havoc mutations + structure-aware seeds
   (what most Python teams run in CI).
2. **Hypothesis** properties in ``tests/core/test_wire_properties.py``.
3. Optional path: compile a tiny C shim later and point AFL at it; same
   decode entrypoints.

Usage
-----
::

    PYTHONPATH=src python scripts/fuzz_wire.py --seconds 30 --jobs 4
    PYTHONPATH=src python scripts/fuzz_wire.py --pytest-budget   # short CI mode

Exit code 0 if no crashes (uncaught non-ValueError exceptions).
"""

from __future__ import annotations

import argparse
import os
import random
import struct
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

# allow running from repo root
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from ux_channel.wire import available_formats, decode, try_decode  # noqa: E402
from ux_channel.wire.cxb import encode_cxb  # noqa: E402
from ux_channel.wire.core import encode  # noqa: E402


# ---------------------------------------------------------------------------
# Corpus seeds
# ---------------------------------------------------------------------------


def _seed_docs() -> list[dict]:
    return [
        {"v": "1", "ok": True, "ops": []},
        {
            "v": "1",
            "ok": True,
            "ops": [{"op": "toast", "message": "hi", "level": "info"}],
        },
        {
            "v": "1",
            "ok": False,
            "ops": [],
            "error": {"code": "x", "message": "y"},
        },
        {
            "v": "1",
            "action": "Cart.add",
            "args": {"sku": "a", "n": 1},
            "cap": "tok",
        },
        {
            "v": "1",
            "ok": True,
            "ops": [
                {
                    "op": "morph",
                    "target": '[data-channel-id="c"]',
                    "html": "<div>" + ("x" * 400) + "</div>",
                    "morph": "idiomorph",
                }
            ]
            * 3,
        },
        {"nested": {"a": [1, 2, {"b": True}]}, "u": "café ☕"},
    ]


def build_seed_corpus() -> list[bytes]:
    seeds: list[bytes] = [
        b"",
        b"{}",
        b"[]",
        b"null",
        b"\x00",
        b"CXB1",
        b"CXBZ",
        b"\xff\xfe",
        MAGIC_LIKE := b"CXB1\x02\x00",
    ]
    for doc in _seed_docs():
        for fmt in available_formats():
            try:
                seeds.append(bytes(encode(doc, format=fmt).data))
            except Exception:
                pass
        try:
            seeds.append(encode_cxb(doc if isinstance(doc, dict) else {"x": doc}))
        except Exception:
            pass
    # interesting integers / lengths as fake frames
    for n in (0, 1, 2, 127, 128, 255, 256, 65535, 2**20):
        seeds.append(struct.pack(">I", n & 0xFFFFFFFF) + b"A" * min(n, 64))
    return seeds


# ---------------------------------------------------------------------------
# Mutations (AFL-inspired)
# ---------------------------------------------------------------------------


def _mut_bitflip(data: bytearray, rng: random.Random) -> None:
    if not data:
        data.append(rng.randrange(256))
        return
    i = rng.randrange(len(data))
    data[i] ^= 1 << rng.randrange(8)


def _mut_byte_set(data: bytearray, rng: random.Random) -> None:
    if not data:
        data.append(rng.randrange(256))
        return
    data[rng.randrange(len(data))] = rng.randrange(256)


def _mut_interesting(data: bytearray, rng: random.Random) -> None:
    vals = [0, 1, 0x7F, 0x80, 0xFF, 0x100, 0xFFFF, 0x80000000]
    v = rng.choice(vals)
    raw = struct.pack(">I", v & 0xFFFFFFFF)
    if not data:
        data.extend(raw)
        return
    i = rng.randrange(len(data))
    for j, b in enumerate(raw):
        if i + j < len(data):
            data[i + j] = b


def _mut_insert(data: bytearray, rng: random.Random) -> None:
    i = rng.randrange(len(data) + 1)
    n = rng.randint(1, 16)
    data[i:i] = bytes(rng.randrange(256) for _ in range(n))


def _mut_delete(data: bytearray, rng: random.Random) -> None:
    if len(data) < 2:
        return
    i = rng.randrange(len(data))
    n = rng.randint(1, min(16, len(data) - i))
    del data[i : i + n]


def _mut_splice(data: bytearray, rng: random.Random, corpus: list[bytes]) -> None:
    if not corpus:
        return
    other = corpus[rng.randrange(len(corpus))]
    if not other:
        return
    chunk = other[rng.randrange(len(other)) :][: rng.randint(1, 32)]
    i = rng.randrange(len(data) + 1)
    data[i:i] = chunk


def _mut_havoc(data: bytearray, rng: random.Random, corpus: list[bytes]) -> None:
    for _ in range(rng.randint(1, 8)):
        op = rng.choice(
            [_mut_bitflip, _mut_byte_set, _mut_interesting, _mut_insert, _mut_delete]
        )
        if op is _mut_delete:
            op(data, rng)
        else:
            op(data, rng)
    if rng.random() < 0.3:
        _mut_splice(data, rng, corpus)
    # cap size
    if len(data) > 8192:
        del data[8192:]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

# Exceptions that mean "invalid input" — not a fuzzer crash
_OK_EXC = (
    ValueError,
    TypeError,
    UnicodeDecodeError,
    UnicodeError,
    OverflowError,
    struct.error,
    MemoryError,  # treat as limit, not crash for budgeted fuzz
)


@dataclass
class FuzzStats:
    iterations: int = 0
    ok_decodes: int = 0
    expected_errors: int = 0
    crashes: int = 0
    unique_crashes: set[str] = field(default_factory=set)
    by_format: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "iterations": self.iterations,
            "ok_decodes": self.ok_decodes,
            "expected_errors": self.expected_errors,
            "crashes": self.crashes,
            "unique_crashes": sorted(self.unique_crashes)[:20],
            "by_format": dict(self.by_format),
        }


def _run_one(data: bytes, fmt: str, stats: FuzzStats) -> None:
    stats.iterations += 1
    stats.by_format[fmt] = stats.by_format.get(fmt, 0) + 1
    try:
        decode(data, format=fmt)
        stats.ok_decodes += 1
    except _OK_EXC:
        stats.expected_errors += 1
    except Exception as exc:  # noqa: BLE001 — anything else is a crash for us
        # orjson.JSONDecodeError subclasses ValueError on some versions
        name = type(exc).__module__ + "." + type(exc).__name__
        if "DecodeError" in name or "UnpackException" in name or "ExtraData" in name:
            stats.expected_errors += 1
            return
        key = f"{fmt}:{name}:{str(exc)[:120]}"
        if key not in stats.unique_crashes:
            stats.unique_crashes.add(key)
            stats.crashes += 1
            print("CRASH", key, file=sys.stderr)
            traceback.print_exc()


def fuzz_for(
    seconds: float = 5.0,
    *,
    seed: int = 0,
    max_iters: int | None = None,
) -> FuzzStats:
    rng = random.Random(seed)
    corpus = build_seed_corpus()
    stats = FuzzStats()
    fmts = available_formats()
    t_end = time.monotonic() + seconds
    i = 0
    while time.monotonic() < t_end:
        if max_iters is not None and i >= max_iters:
            break
        i += 1
        base = bytearray(corpus[rng.randrange(len(corpus))])
        _mut_havoc(base, rng, corpus)
        data = bytes(base)
        # occasionally keep mutant as new seed (AFL-like)
        if rng.random() < 0.05 and 0 < len(data) < 4096 and len(corpus) < 500:
            corpus.append(data)
        fmt = fmts[rng.randrange(len(fmts))]
        _run_one(data, fmt, stats)
        # also try_decode total function
        try_decode(data, format=fmt, default=None)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mutational fuzzer for ux-channel wire codecs")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-iters", type=int, default=None)
    ap.add_argument(
        "--pytest-budget",
        action="store_true",
        help="Short deterministic run for CI (~2s / 3000 iters)",
    )
    args = ap.parse_args(argv)
    if args.pytest_budget:
        args.seconds = 2.0
        args.max_iters = 3000
        args.seed = 42
    stats = fuzz_for(args.seconds, seed=args.seed, max_iters=args.max_iters)
    print("FUZZ_RESULT", stats.as_dict())
    return 1 if stats.crashes else 0


if __name__ == "__main__":
    raise SystemExit(main())
