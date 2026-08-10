#!/usr/bin/env python3
"""Minimal self-contained harness: validate conformance JSON vectors.

No dependency on the ux-channel package. Run from anywhere:

    python3 conformance/harness/validate_json_vectors.py

Exit 0 = all checks passed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.json"
VECTORS = ROOT / "vectors"


def load(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def check_intent(doc: dict, name: str) -> list[str]:
    errs = []
    if doc.get("v") != "1":
        errs.append(f"{name}: v must be '1'")
    if not isinstance(doc.get("action"), str) or not doc["action"]:
        errs.append(f"{name}: action required non-empty string")
    if "args" in doc and not isinstance(doc["args"], dict):
        errs.append(f"{name}: args must be object when present")
    return errs


def check_result(doc: dict, name: str) -> list[str]:
    errs = []
    if "ok" not in doc or not isinstance(doc["ok"], bool):
        errs.append(f"{name}: ok required boolean")
    if not doc["ok"]:
        err = doc.get("error")
        if not isinstance(err, dict) or "code" not in err or "message" not in err:
            errs.append(f"{name}: error.code and error.message required when ok=false")
    ops = doc.get("ops", [])
    if not isinstance(ops, list):
        errs.append(f"{name}: ops must be array")
    else:
        for i, op in enumerate(ops):
            if not isinstance(op, dict) or "op" not in op:
                errs.append(f"{name}: ops[{i}] must have 'op'")
    if "trace" in doc:
        tr = doc["trace"]
        if not isinstance(tr, dict) or "intent_id" not in tr:
            errs.append(f"{name}: trace.intent_id required when trace present")
        hops = tr.get("hops", [])
        if not isinstance(hops, list):
            errs.append(f"{name}: trace.hops must be array")
    return errs


def main() -> int:
    if not MANIFEST.exists():
        print("manifest.json missing", file=sys.stderr)
        return 2
    manifest = load(MANIFEST)
    errors: list[str] = []
    checked = 0

    for category, entries in manifest.get("vectors", {}).items():
        for entry in entries:
            rel = entry["file"]
            path = VECTORS / rel
            if rel.endswith(".md"):
                if not path.exists():
                    errors.append(f"missing notes: {rel}")
                continue
            if not path.exists():
                errors.append(f"missing vector: {rel}")
                continue
            doc = load(path)
            checked += 1
            if category == "intent":
                errors.extend(check_intent(doc, rel))
            elif category in ("result", "trace"):
                errors.extend(check_result(doc, rel))
            # round-trip stability
            roundtrip = json.loads(json.dumps(doc, sort_keys=True))
            if json.dumps(doc, sort_keys=True) != json.dumps(roundtrip, sort_keys=True):
                errors.append(f"{rel}: json round-trip unstable")

    print(f"Checked {checked} JSON vectors")
    if errors:
        print("FAILURES:")
        for e in errors:
            print(" -", e)
        return 1
    print("All structural checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
