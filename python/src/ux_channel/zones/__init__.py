"""Package map navigator — generated catalog, not an implementation layer.

    from ux_channel.zones import catalog, help_public
    print(help_public())
"""
from __future__ import annotations

import json
from pathlib import Path

_CAT = Path(__file__).resolve().parent / "catalog.json"
catalog: dict = json.loads(_CAT.read_text(encoding="utf-8"))

__all__ = ["catalog", "help_public", "help_package"]


def help_public() -> str:
    pe = catalog.get("public_entry", {})
    rp = catalog.get("rust_parity", {})
    lines = [
        "Public entry: " + str(pe.get("preferred", "ux_channel.day1")),
        "Host: " + ", ".join(pe.get("host_api", [])),
        "Cap (Rust-parity): " + ", ".join(pe.get("cap_api", [])),
        "Rust parity map: " + ", ".join(f"{k}→{v}" for k, v in rp.items()),
    ]
    return "\n".join(lines) + "\n"


def help_package(name: str) -> str:
    members = catalog.get(name)
    if not members:
        return f"unknown package: {name}\n"
    rows = "\n".join(f"  {k:28} {v}" for k, v in sorted(members.items()))
    return f"package={name}\n{rows}\n"
