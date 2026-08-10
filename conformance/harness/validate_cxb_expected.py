#!/usr/bin/env python3
"""Validate CXB expected blobs against the pure-Python oracle.

Full oracle checks (decode + re-encode byte identity) run when
``ux_channel.wire.cxb`` is importable. Otherwise structural checks only
(magic, length, sha256, ~CRC).

  python3 conformance/harness/validate_cxb_expected.py
  UX_CHANNEL_SRC=/path/to/ux-channel/src python3 ...
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import zlib
from pathlib import Path

CONF = Path(__file__).resolve().parents[1]  # conformance/
PKG = CONF.parent  # package root


def _try_import_oracle():
    candidates = []
    if os.environ.get("UX_CHANNEL_SRC"):
        candidates.append(Path(os.environ["UX_CHANNEL_SRC"]))
    candidates.extend(
        [
            PKG / "python" / "src",  # monorepo layout
            PKG / "src",
            Path("/tmp/uxc-pkg/ux-channel-0.1.0/src"),
            PKG / "ref" / "src",
            PKG.parent / "ux-channel-0.1.0" / "src",
        ]
    )
    for p in candidates:
        if p.is_dir():
            sys.path.insert(0, str(p))
    try:
        from ux_channel.wire.cxb import (  # type: ignore
            decode_cxb_python,
            encode_cxb_python,
            is_cxb,
        )

        return encode_cxb_python, decode_cxb_python, is_cxb
    except Exception:
        return None, None, None


def _frame_bytes(blob: bytes) -> bytes:
    """Return the uncompressed CXB1 frame (including magic + ~CRC)."""
    if blob[:4] == b"CXB1":
        return blob
    if blob[:4] == b"CXBZ":
        inner = zlib.decompress(blob[4:])
        if inner[:4] == b"CXB1":
            return inner
        return b"CXB1" + inner
    raise ValueError(f"bad magic {blob[:4]!r}")


def _verify_crc(blob: bytes) -> None:
    frame = _frame_bytes(blob)
    if len(frame) < 12 or frame[-8:-4] != b"~CRC":
        raise ValueError("missing ~CRC trailer")
    want = struct.unpack(">I", frame[-4:])[0]
    got = zlib.crc32(frame[4:-8]) & 0xFFFFFFFF
    if want != got:
        raise ValueError(f"CRC mismatch want={want:08x} got={got:08x}")


def main() -> int:
    index_path = CONF / "expected" / "cxb" / "index.json"
    if not index_path.is_file():
        print(f"missing {index_path}", file=sys.stderr)
        return 2
    index = json.loads(index_path.read_text())
    vectors = index.get("vectors") or []
    encode_cxb, decode_cxb, is_cxb = _try_import_oracle()
    oracle = encode_cxb is not None

    checked = 0
    failures: list[str] = []

    for entry in vectors:
        # entry["file"] is relative to package root: expected/cxb/foo.cxb
        path = PKG / entry["file"]
        if not path.is_file():
            path = CONF / "expected" / "cxb" / Path(entry["file"]).name
        if not path.is_file():
            failures.append(f"missing blob: {entry['file']}")
            continue

        blob = path.read_bytes()
        if hashlib.sha256(blob).hexdigest() != entry.get("sha256"):
            failures.append(f"{entry['file']}: sha256 mismatch")
            continue
        if len(blob) != entry.get("len"):
            failures.append(f"{entry['file']}: len mismatch")
            continue
        if blob[:4] not in (b"CXB1", b"CXBZ"):
            failures.append(f"{entry['file']}: bad magic")
            continue
        try:
            _verify_crc(blob)
        except Exception as e:
            failures.append(f"{entry['file']}: crc {e}")
            continue

        if oracle:
            src = CONF / entry["source"]  # vectors/...
            if not src.is_file():
                failures.append(f"{entry['file']}: missing source {entry['source']}")
                continue
            doc = json.loads(src.read_text())
            try:
                if not is_cxb(blob):
                    failures.append(f"{entry['file']}: is_cxb false")
                    continue
                decoded = decode_cxb(blob)
                if "action" in doc and decoded.get("action") != doc.get("action"):
                    failures.append(f"{entry['file']}: action mismatch after decode")
                    continue
                if "ok" in doc and decoded.get("ok") != doc.get("ok"):
                    failures.append(f"{entry['file']}: ok mismatch after decode")
                    continue
                again = encode_cxb(doc)
                if again != blob:
                    failures.append(
                        f"{entry['file']}: re-encode mismatch "
                        f"(got {len(again)}b "
                        f"sha={hashlib.sha256(again).hexdigest()[:12]})"
                    )
                    continue
            except Exception as e:
                failures.append(f"{entry['file']}: oracle {e}")
                continue

        checked += 1

    mode = "oracle+structural" if oracle else "structural-only"
    print(f"Checked {checked}/{len(vectors)} CXB expected blobs ({mode})")
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f" - {f}")
        return 1
    print("All CXB expected checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
