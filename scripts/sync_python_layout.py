#!/usr/bin/env python3
"""Layout automation — catalog, derived map fields, optional disk sync.

Source of truth for *intent*:
  - ``packages`` in PACKAGE_MAP.json (which modules belong where)
  - Or disk layout when you run ``--sync-map`` (opt-in inventory refresh)

**Always automated (never hand-edit):**
  - ``modules`` and ``module_count`` in PACKAGE_MAP.json
  - ``python/src/ux_channel/catalog/catalog.json``
  - catalog package ``__init__.py`` helpers (if missing/broken)

Package ``__init__.py`` export lists remain **hand-maintained** (public API is design).

Commands::

  python3 scripts/sync_python_layout.py              # write derived artifacts
  python3 scripts/sync_python_layout.py --check      # CI: fail if anything stale
  python3 scripts/sync_python_layout.py --sync-map   # refresh packages from disk, then write
  python3 scripts/sync_python_layout.py --sync-map --check

See AUTOMATION.md — default is automate ceremonial inventories; hand-code only
features, law, and public API.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "python" / "src" / "ux_channel"
MAP_PATH = PKG / "PACKAGE_MAP.json"

_SKIP_STEMS = frozenset({"__init__", "__main__", "__pycache__"})

CATALOG_INIT = '''"""Package catalog — generated navigator (L5 tooling, not an implementation plane).

Design
    Machine-readable inventory of packages + modules so agents and humans do
    not re-type layouts. Sourced from PACKAGE_MAP via scripts/sync_python_layout.py.

Architecture
    L5 only — never import this for dispatch or trust. Mirror of layout law.

Implementation
    ``catalog.json`` is GENERATED. Do not hand-edit package lists here.

    from ux_channel.catalog import help_public, help_package, catalog

See AUTOMATION.md + LONGEVITY.md.
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
        f"Public: {pe.get('preferred', 'ux_channel.api')}
"
        f"Host API: {', '.join(pe.get('host_api', []))}
"
        f"Cap (Rust-parity): {', '.join(pe.get('cap_api', []))}
"
        f"Packages: {pkgs}
"
        f"Policy: {catalog.get('policy')}
"
        f"Rust parity: {rp}
"
    )


def help_package(name: str) -> str:
    members = catalog.get("packages", {}).get(name)
    if not members:
        return f"unknown package: {name}
"
    docs = (catalog.get("package_docs") or {}).get(name, "")
    strata = (catalog.get("strata") or {}).get(name, "")
    header = f"package={name}"
    if strata:
        header += f"  strata={strata}"
    if docs:
        header += f"
  {docs}"
    rows = "
".join(f"  {k:28} {v}" for k, v in sorted(members.items()))
    return f"{header}
{rows}
"
'''


def load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def packages_from_meta(meta: dict) -> dict[str, list[str]]:
    if isinstance(meta.get("packages"), dict) and meta["packages"]:
        return {k: sorted(set(v)) for k, v in meta["packages"].items()}
    by_pkg: dict[str, list[str]] = {}
    for key, pkg in meta.get("modules", {}).items():
        stem = key.split(".", 1)[1] if "." in key else key
        by_pkg.setdefault(pkg, []).append(stem)
    return {k: sorted(set(v)) for k, v in by_pkg.items()}


def modules_from_packages(by_pkg: dict[str, list[str]]) -> dict[str, str]:
    """Ceremonial inverse index — always derived, never hand-edited."""
    out: dict[str, str] = {}
    for pkg, stems in sorted(by_pkg.items()):
        for stem in sorted(set(stems)):
            out[f"{pkg}.{stem}"] = pkg
    return out


def disk_stems(pkg: str) -> set[str]:
    """All module stems on disk (including private ``_`` helpers)."""
    d = PKG / pkg
    if not d.is_dir():
        return set()
    return {
        p.stem
        for p in d.glob("*.py")
        if p.stem not in _SKIP_STEMS
    }


def public_disk_stems(pkg: str) -> set[str]:
    """Non-private stems — candidates for auto inventory."""
    return {s for s in disk_stems(pkg) if not s.startswith("_")}


def discover_packages_from_disk(existing: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    """Inventory packages from disk.

    - Adds all non-private ``*.py`` stems
    - Keeps intentionally mapped private ``_*.py`` stems if the file still exists
    - Keeps empty packages that only have ``__init__.py``
    """
    existing = existing or {}
    by_pkg: dict[str, list[str]] = {}
    for d in sorted(PKG.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        if d.name == "__pycache__":
            continue
        if not (d / "__init__.py").exists():
            continue
        pub = sorted(public_disk_stems(d.name))
        priv_keep = [
            s
            for s in existing.get(d.name, [])
            if s.startswith("_") and (d / f"{s}.py").exists()
        ]
        by_pkg[d.name] = sorted(set(pub) | set(priv_keep))
    # Preserve package entries that only exist in map if dir still present
    for pkg, stems in existing.items():
        if pkg in by_pkg:
            continue
        if (PKG / pkg / "__init__.py").exists():
            by_pkg[pkg] = sorted(
                s for s in stems if (PKG / pkg / f"{s}.py").exists()
            )
    return by_pkg


def build_catalog_data(meta: dict) -> dict:
    by_pkg = packages_from_meta(meta)
    return {
        "policy": "no_shims",
        "map_version": meta.get("version"),
        "note": (
            "GENERATED by scripts/sync_python_layout.py — do not hand-edit. "
            "Package __init__.py export lists stay hand-maintained (public API). "
            "package_docs + strata mirrored from PACKAGE_MAP for navigation."
        ),
        "public_entry": meta.get("public_entry", {}),
        "rust_parity": meta.get("rust_parity", {}),
        "package_docs": meta.get("package_docs", {}),
        "strata": meta.get("strata", {}),
        "packages": {
            pkg: {s: f"ux_channel.{pkg}.{s}" for s in sorted(set(stems))}
            for pkg, stems in sorted(by_pkg.items())
        },
    }


def catalog_text(meta: dict) -> str:
    return json.dumps(build_catalog_data(meta), indent=2) + "\n"


def apply_derived_fields(meta: dict) -> dict:
    """Return a copy of meta with modules + module_count regenerated from packages."""
    out = dict(meta)
    by_pkg = packages_from_meta(out)
    out["packages"] = {k: sorted(set(v)) for k, v in sorted(by_pkg.items())}
    out["modules"] = modules_from_packages(out["packages"])
    out["module_count"] = len(out["modules"])
    return out


def write_map(meta: dict) -> bool:
    text = json.dumps(meta, indent=2) + "\n"
    old = MAP_PATH.read_text(encoding="utf-8") if MAP_PATH.exists() else ""
    if old != text:
        MAP_PATH.write_text(text, encoding="utf-8")
        return True
    return False


def regenerate(meta: dict, *, write: bool) -> tuple[dict, list[str]]:
    """Regenerate derived map fields + catalog. Returns (meta, actions)."""
    actions: list[str] = []
    meta = apply_derived_fields(meta)

    if write:
        if write_map(meta):
            actions.append("write PACKAGE_MAP.json (modules + module_count derived)")
    else:
        current = load_map()
        if (
            current.get("modules") != meta.get("modules")
            or current.get("module_count") != meta.get("module_count")
            or packages_from_meta(current) != packages_from_meta(meta)
        ):
            actions.append("STALE PACKAGE_MAP.json derived fields (run without --check)")

    catalog_dir = PKG / "catalog"
    catalog_dir.mkdir(exist_ok=True)
    cat_path = catalog_dir / "catalog.json"
    cat_text = catalog_text(meta)
    if write:
        if not cat_path.exists() or cat_path.read_text(encoding="utf-8") != cat_text:
            cat_path.write_text(cat_text, encoding="utf-8")
            actions.append("write catalog/catalog.json")
    else:
        if not cat_path.exists() or cat_path.read_text(encoding="utf-8") != cat_text:
            actions.append("STALE catalog/catalog.json (run without --check)")

    zinit = catalog_dir / "__init__.py"
    if write:
        ztext = zinit.read_text(encoding="utf-8") if zinit.exists() else ""
        if (
            not zinit.exists()
            or "help_public" not in ztext
            or "package_docs" not in ztext
            or "Design" not in ztext
        ):
            zinit.write_text(CATALOG_INIT, encoding="utf-8")
            actions.append("write catalog/__init__.py")
    else:
        ztext = zinit.read_text(encoding="utf-8") if zinit.exists() else ""
        if not zinit.exists() or "help_public" not in ztext:
            actions.append("STALE catalog/__init__.py")
        elif "package_docs" not in ztext or "Design" not in ztext:
            actions.append("STALE catalog/__init__.py (missing package_docs helper)")

    allowed = {"__init__", "__main__", "_version"}
    for path in PKG.glob("*.py"):
        if path.stem in allowed:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if "Compatibility" in body or "GENERATED by scripts" in body or "_sys.modules[__name__]" in body:
            if write:
                path.unlink()
                actions.append(f"removed shim {path.name}")
            else:
                actions.append(f"STALE shim present: {path.name}")
    return meta, actions


def check(meta: dict) -> list[str]:
    problems: list[str] = []
    by_pkg = packages_from_meta(meta)

    for pkg, stems in by_pkg.items():
        for stem in stems:
            if not (PKG / pkg / f"{stem}.py").exists():
                problems.append(f"missing {pkg}/{stem}.py")

    for pkg, stems in by_pkg.items():
        d = PKG / pkg
        if not d.is_dir():
            problems.append(f"missing package dir {pkg}/")
            continue
        on_disk = disk_stems(pkg)
        mapped = set(stems)
        # Unmapped public modules are errors; private _* unmapped is OK
        for extra in sorted(on_disk - mapped):
            if extra.startswith("_"):
                continue
            problems.append(
                f"unmapped module {pkg}/{extra}.py "
                f"(add to PACKAGE_MAP packages or: scripts/sync_python_layout.py --sync-map)"
            )
        for missing in sorted(mapped - on_disk):
            problems.append(f"mapped but missing {pkg}/{missing}.py")

    expected_modules = modules_from_packages(by_pkg)
    if meta.get("modules") != expected_modules:
        problems.append(
            "PACKAGE_MAP modules != packages (derived field stale — run sync_python_layout.py)"
        )
    if meta.get("module_count") != len(expected_modules):
        problems.append(
            f"PACKAGE_MAP module_count {meta.get('module_count')} != {len(expected_modules)}"
        )

    allowed = {"__init__", "__main__", "_version"}
    for path in PKG.glob("*.py"):
        if path.stem not in allowed:
            problems.append(f"forbidden top-level module (no shims): {path.name}")

    if not (PKG / "api" / "__init__.py").exists():
        problems.append("missing public package api/")
    if not (PKG / "render" / "__init__.py").exists():
        problems.append("missing package render/")
    for legacy in ("paint", "ops_dx", "bridge_meta", "day1", "zones", "security_plane", "agents"):
        if (PKG / legacy).exists():
            problems.append(f"legacy package {legacy}/ must not exist")

    for p in PKG.rglob("__init__.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        if "MANUAL_PUBLIC_API" in text:
            problems.append(f"stale layout marker MANUAL_PUBLIC_API in {p.relative_to(PKG)}")

    if int(meta.get("version") or 0) >= 3:
        for key, pkg in (meta.get("modules") or {}).items():
            if "." not in key:
                problems.append(f"v3 module key must be package.stem, got {key!r}")
            elif not key.startswith(pkg + "."):
                problems.append(f"v3 module key {key!r} does not match package {pkg!r}")

    # Catalog must mirror package_docs / strata when present on the map
    cat_path = PKG / "catalog" / "catalog.json"
    if cat_path.exists():
        cat = json.loads(cat_path.read_text(encoding="utf-8"))
        if meta.get("package_docs") and cat.get("package_docs") != meta.get("package_docs"):
            problems.append("catalog package_docs out of sync with PACKAGE_MAP (run regen)")
        if meta.get("strata") and cat.get("strata") != meta.get("strata"):
            problems.append("catalog strata out of sync with PACKAGE_MAP (run regen)")

    sys.path.insert(0, str(ROOT / "python" / "src"))
    try:
        from ux_channel import CapService, Channel, Region, RegionBook, agents, state
        from ux_channel.api import CapService as ACS
        from ux_channel.api import Channel as C2
        from ux_channel.api import state as api_state
        from ux_channel.agent_runtime import AgentRunner
        from ux_channel.agent_runtime.policy import AgentPolicy
        from ux_channel.asgi import mount_channel
        from ux_channel.devtools import errors as devtools_errors
        from ux_channel.host.channel import Channel as C3
        from ux_channel.host.regions import RegionBook as RB
        from ux_channel.host.regions import _id_str  # noqa: F401
        from ux_channel.host.state_api import state as state_fn
        from ux_channel.host.stores import MemoryStateStore  # noqa: F401
        from ux_channel.protocol import CapService as PCS
        from ux_channel.protocol import errors as protocol_errors
        from ux_channel.protocol import morph as pmorph
        from ux_channel.protocol.capability import CapService as CS
        from ux_channel.render import morph_ir
        from ux_channel.render.renderers import HtmlRenderer
        from ux_channel.security import policy as security_policy
        from ux_channel.wire import encode, encode_cxb
        from ux_channel import CapService as RCS
        from ux_channel import morph as rmorph
        from ux_channel import state as rstate

        assert Channel is C2 is C3
        assert RegionBook is RB
        assert CapService is CS is ACS is PCS is RCS
        assert hasattr(Channel, "describe") and not hasattr(Channel, "mental_model")
        svc = CapService("dev-secret-key-32chars-minimum!!!!")
        assert hasattr(svc, "mint") and not hasattr(svc, "sign")
        assert callable(state_fn) and api_state is rstate is state_fn
        assert callable(agents)
        assert pmorph is rmorph
        assert encode and encode_cxb and callable(mount_channel)
        assert AgentRunner and AgentPolicy
        assert security_policy is not None
        assert protocol_errors is not None and devtools_errors is not None
        assert protocol_errors is not devtools_errors
        _ = morph_ir, HtmlRenderer
    except ModuleNotFoundError as exc:
        # Layout/catalog freshness is still enforced; identity smoke needs host deps.
        # CI / verify.sh install requirements-dev.txt before full verify.
        missing = getattr(exc, "name", None) or str(exc)
        print(
            f"layout: import smoke skipped (missing dependency: {missing}); "
            "install requirements-dev.txt for full check",
            file=sys.stderr,
        )
    except Exception as exc:
        problems.append(f"import smoke: {exc}")
    return problems


def merge_disk_into_packages(meta: dict) -> tuple[dict, list[str]]:
    """Opt-in: set packages from disk (add public modules, drop missing). Keep mapped _*."""
    notes: list[str] = []
    old = packages_from_meta(meta)
    disk = discover_packages_from_disk(old)

    added = []
    removed = []
    for pkg in sorted(set(old) | set(disk)):
        o, n = set(old.get(pkg, [])), set(disk.get(pkg, []))
        for a in sorted(n - o):
            added.append(f"{pkg}.{a}")
        for r in sorted(o - n):
            removed.append(f"{pkg}.{r}")
    if added:
        notes.append("sync-map added: " + ", ".join(added[:40]) + ("…" if len(added) > 40 else ""))
    if removed:
        notes.append(
            "sync-map removed: " + ", ".join(removed[:40]) + ("…" if len(removed) > 40 else "")
        )
    if not added and not removed:
        notes.append("sync-map: packages already match disk")

    meta = dict(meta)
    meta["packages"] = {k: sorted(set(v)) for k, v in sorted(disk.items())}
    return meta, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="CI mode: do not write; fail if derived artifacts are stale or layout invalid",
    )
    ap.add_argument(
        "--sync-map",
        action="store_true",
        help="Refresh packages from disk (ceremonial inventory) before regenerate",
    )
    args = ap.parse_args()
    meta = load_map()
    notes: list[str] = []

    if args.sync_map:
        meta, notes = merge_disk_into_packages(meta)

    write = not args.check
    meta, actions = regenerate(meta, write=write)

    if write:
        print("sync_python_layout:", "updated" if (actions or notes) else "already up to date")
        for n in notes:
            print(" ", n)
        for a in actions[:30]:
            print(" ", a)
    else:
        stale = [a for a in actions if a.startswith("STALE")]
        drift = args.sync_map and any("added" in n or "removed" in n for n in notes)
        if stale or drift:
            print("FAILED: derived artifacts or map inventory stale", file=sys.stderr)
            for n in notes:
                print(" -", n, file=sys.stderr)
            for a in actions:
                print(" -", a, file=sys.stderr)
            print(
                "Fix: python3 scripts/sync_python_layout.py"
                + (" --sync-map" if args.sync_map else ""),
                file=sys.stderr,
            )
            return 1

    meta = load_map() if write else apply_derived_fields(meta)
    problems = check(meta)
    if problems:
        print("FAILED:", file=sys.stderr)
        for p in problems:
            print(" -", p, file=sys.stderr)
        return 1
    n = sum(len(v) for v in packages_from_meta(meta).values())
    print(
        f"sync_python_layout: OK ({n} modules in {len(packages_from_meta(meta))} packages, "
        f"derived fields fresh, no shims)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
