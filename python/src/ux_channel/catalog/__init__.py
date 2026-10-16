"""Package catalog — generated navigator (L5 tooling, not an implementation plane).

Design
    Machine-readable inventory of packages + modules so agents and humans do
    not re-type layouts. Sourced from PACKAGE_MAP via scripts/sync_python_layout.py.

Architecture
    L5 only — never import this for dispatch or trust. Mirror of layout law.

Implementation
    ``catalog.json`` is GENERATED. Do not hand-edit package lists here.

    from ux_channel.catalog import help_public, help_package, catalog

See AUTOMATION.md + LONGEVITY.md.\n"""
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
        f"Public: {pe.get('preferred', 'ux_channel.api')}\n"
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
    docs = (catalog.get("package_docs") or {}).get(name, "")
    strata = (catalog.get("strata") or {}).get(name, "")
    header = f"package={name}"
    if strata:
        header += f"  strata={strata}"
    if docs:
        header += f"\n  {docs}"
    rows = "\n".join(f"  {k:28} {v}" for k, v in sorted(members.items()))
    return f"{header}\n{rows}\n"
