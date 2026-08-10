"""Package navigator (not an implementation layer).

    from ux_channel.zones import help_public, catalog
"""
from __future__ import annotations

import json
from pathlib import Path

catalog = json.loads((Path(__file__).parent / "catalog.json").read_text(encoding="utf-8"))
__all__ = ["catalog", "help_public", "help_package"]


def help_public() -> str:
    pe = catalog.get("public_entry", {})
    rp = catalog.get("rust_parity", {})
    pkgs = ", ".join(sorted(catalog.get("packages", {})))
    return (
        f"Public: {pe.get('preferred', 'ux_channel.day1')}\n"
        f"Host API: {', '.join(pe.get('host_api', []))}\n"
        f"Cap (Rust-parity): {', '.join(pe.get('cap_api', []))}\n"
        f"Packages: {pkgs}\n"
        f"Policy: {catalog.get('policy')}\n"
        f"Rust parity: {rp}\n"
    )


def help_package(name: str) -> str:
    members = catalog.get("packages", {}).get(name)
    if not members:
        return f"unknown package: {name}\n"
    rows = "\n".join(f"  {k:28} {v}" for k, v in sorted(members.items()))
    return f"package={name}\n{rows}\n"
