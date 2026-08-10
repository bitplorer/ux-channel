#!/usr/bin/env python3
"""Regenerate conformance/expected/cxb from the pure-Python CXB oracle.

  PYTHONPATH=/path/to/ux-channel/src python3 conformance/harness/regenerate_cxb_expected.py
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

CONF = Path(__file__).resolve().parents[1]
PKG = CONF.parent


def main() -> int:
    if os.environ.get("UX_CHANNEL_SRC"):
        sys.path.insert(0, os.environ["UX_CHANNEL_SRC"])
    for p in [
        Path("/tmp/uxc-pkg/ux-channel-0.1.0/src"),
        PKG / "ref" / "src",
    ]:
        if p.is_dir():
            sys.path.insert(0, str(p))
    try:
        from ux_channel.wire.cxb import (  # type: ignore
            MAGIC,
            MAGIC_Z,
            MEDIA_TYPE,
            decode_cxb_python,
            encode_cxb_python,
            is_cxb,
        )
    except ImportError as e:
        print(f"need ux_channel oracle: {e}", file=sys.stderr)
        return 2

    out = CONF / "expected" / "cxb"
    out.mkdir(parents=True, exist_ok=True)
    # clear previous .cxb / .meta.json (keep index rebuild)
    for old in out.glob("*"):
        if old.name == "README.md":
            continue
        if old.suffix in {".cxb", ".json"} or old.name.endswith(".meta.json"):
            old.unlink()

    index = {
        "suite": "ux-channel-cxb-expected-0.1",
        "oracle": "ux_channel.wire.cxb.encode_cxb_python",
        "package_version": "0.1.0",
        "media_type": MEDIA_TYPE,
        "magic": MAGIC.decode(),
        "magic_z": MAGIC_Z.decode(),
        "vectors": [],
    }

    for cat in ("intent", "result", "trace"):
        d = CONF / "vectors" / cat
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            doc = json.loads(path.read_text())
            blob = encode_cxb_python(doc)
            assert is_cxb(blob), path
            decode_cxb_python(blob)  # must succeed
            bname = f"{cat}__{path.stem}.cxb"
            (out / bname).write_bytes(blob)
            meta = {
                "source": f"vectors/{cat}/{path.name}",
                "file": f"expected/cxb/{bname}",
                "category": cat,
                "magic": blob[:4].decode("latin1"),
                "len": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "sha256_prefix": hashlib.sha256(blob).hexdigest()[:16],
            }
            side = {
                **meta,
                "hex": blob.hex(),
                "b64": base64.b64encode(blob).decode(),
            }
            (out / f"{cat}__{path.stem}.meta.json").write_text(
                json.dumps(side, indent=2) + "\n"
            )
            index["vectors"].append(meta)
            print(f"OK {bname:40} {meta['magic']} {meta['len']:5}d  {meta['sha256_prefix']}")

    (out / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"Wrote {len(index['vectors'])} expected CXB blobs → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
