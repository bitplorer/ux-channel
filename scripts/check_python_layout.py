#!/usr/bin/env python3
"""Ensure every top-level ux_channel module is claimed by a zone (no orphan dread)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "python" / "src" / "ux_channel"
CATALOG = PKG / "zones" / "catalog.json"

SKIP = {"__init__", "__init__.py", "__pycache__", "zones", "py.typed"}


def main() -> int:
    if not CATALOG.exists():
        print("missing zones/catalog.json", file=sys.stderr)
        return 1
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    claimed = set()
    for members in catalog.values():
        claimed.update(members.keys())

    top = set()
    for p in PKG.iterdir():
        if p.name in SKIP or p.name.startswith("."):
            continue
        if p.suffix == ".py":
            if p.stem == "__init__":
                continue
            top.add(p.stem)
        elif p.is_dir() and p.name != "__pycache__":
            top.add(p.name)

    orphans = sorted(top - claimed)
    ghosts = sorted(claimed - top - {"py.typed"})  # py.typed is a file without .py stem in iter dirs
    # py.typed is a file named py.typed
    if (PKG / "py.typed").exists():
        top.add("py.typed")
        orphans = sorted(top - claimed)

    if orphans:
        print("Orphan top-level modules (not in any zone):", file=sys.stderr)
        for o in orphans:
            print(f"  - {o}", file=sys.stderr)
        print("Add them to scripts/gen_python_layout.py / zones catalog.", file=sys.stderr)
        return 1
    # ghosts that are only documentation ok
    real_ghosts = [g for g in ghosts if g not in {"py.typed"}]
    # allow claimed names that are files
    real_ghosts = [g for g in sorted(claimed - top) if g != "py.typed"]
    if real_ghosts:
        print("Catalog ghosts (claimed but missing on disk):", real_ghosts, file=sys.stderr)
        return 1

    # import zones
    sys.path.insert(0, str(ROOT / "python" / "src"))
    from ux_channel.zones import ZONES, help_all  # noqa: WPS433

    assert len(ZONES) >= 8
    text = help_all()
    assert "protocol" in text and "host" in text
    print(f"python_layout: OK ({len(top)} top-level → {len(ZONES)} zones)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
