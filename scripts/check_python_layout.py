#!/usr/bin/env python3
"""Ensure cohesive package layout stays complete and importable."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "python" / "src" / "ux_channel"
CATALOG = PKG / "zones" / "catalog.json"

# Top-level dirs that are first-class subpackages (not flat shims)
KNOWN_SUBPACKAGES = {
    "protocol", "host", "paint", "security_plane", "transport",
    "foundations", "realtime", "bridge_meta", "ops_dx",
    "wire", "asgi", "bridges", "components", "agents", "mcp",
    "workplace", "io_adapters", "redis_extra", "scaffold", "static", "zones",
}

SKIP_FILES = {"__init__", "__main__", "_version", "py.typed"}


def main() -> int:
    if not CATALOG.exists():
        print("missing zones/catalog.json", file=sys.stderr)
        return 1
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    # Every cohesive package dir must exist
    for name in KNOWN_SUBPACKAGES:
        if name in ("io_adapters", "redis_extra", "scaffold", "static"):
            if not (PKG / name).exists():
                # optional
                continue
        if not (PKG / name).exists():
            print(f"missing package dir: {name}", file=sys.stderr)
            return 1

    # Every non-shim implementation module lives under a package
    # Top-level .py must be shim or allowed roots
    bad_top = []
    for p in PKG.glob("*.py"):
        if p.stem in SKIP_FILES:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if "Compatibility shim" not in text and p.stem not in SKIP_FILES:
            # __init__ already skipped
            if p.stem not in {"__init__"}:
                bad_top.append(p.name)
    if bad_top:
        print("Top-level modules that are not shims (should live in a package):", bad_top, file=sys.stderr)
        return 1

    # Import smoke
    sys.path.insert(0, str(ROOT / "python" / "src"))
    from ux_channel import Channel, Region, Intent, Result  # noqa: WPS433
    from ux_channel.protocol import PACKAGE as proto  # noqa: WPS433
    from ux_channel.host import PACKAGE as host  # noqa: WPS433
    from ux_channel.capability import CapService  # noqa: WPS433
    from ux_channel.host.dx import Channel as Ch2  # noqa: WPS433
    assert Channel is Ch2
    assert proto == "protocol" and host == "host"
    from ux_channel.zones import ZONES, help_all  # noqa: WPS433
    assert "protocol" in ZONES and "host" in ZONES
    _ = help_all()
    # cap algorithm lock
    h = CapService("conformance-oracle-secret-32chars!!")._hash_args(
        {"sku": "abc-123", "qty": 2}
    )
    assert h == "96e4f83e3793b646323a67f314b51044", h

    print(
        f"python_layout: OK "
        f"(cohesive packages + {sum(1 for _ in PKG.glob('*.py'))} top-level files, "
        f"shims verified, imports OK)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
