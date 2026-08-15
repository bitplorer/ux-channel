"""Import-graph assertions — D4 + no second Cap + no vendor-copy.

Used by ``tests/gate/test_cek_layer_honesty.py``. Importing this module
must not import cek_host / cek_surface (default path stays off).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterable

CHANNEL_ROOT = Path(__file__).resolve().parents[1]  # ux_channel/


def _iter_py(root: Path) -> Iterable[Path]:
    skip = {"__pycache__", ".git", "static"}
    for p in root.rglob("*.py"):
        if any(part in skip for part in p.parts):
            continue
        yield p


def imported_names(path: Path) -> set[str]:
    """Top-level imported module names in a file (best-effort ast)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add((alias.name or "").split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def channel_vendor_copy_hits() -> list[str]:
    """Fail if this tree vendors cek_host / cek_surface source."""
    hits: list[str] = []
    for p in _iter_py(CHANNEL_ROOT):
        # The adapter package is allowed to *name* cek modules.
        rel = p.relative_to(CHANNEL_ROOT)
        if rel.parts and rel.parts[0] == "cek":
            continue
        text = p.read_text(encoding="utf-8")
        if "class Host:" in text and "cek_host" in text and "vendor" in text.lower():
            hits.append(str(rel))
    # Physical vendor trees
    for name in ("cek_host", "cek_surface", "cek-host", "cek-surface"):
        if (CHANNEL_ROOT / name).exists():
            hits.append(name)
    return hits


def cek_surface_imports_ux_channel() -> list[str]:
    """D4: if cek_surface is importable, its module graph must not include ux_channel."""
    try:
        import cek_surface
    except ImportError:
        return []
    hits: list[str] = []
    root = Path(cek_surface.__file__).resolve().parent
    for p in _iter_py(root):
        names = imported_names(p)
        if "ux_channel" in names:
            hits.append(str(p))
    # Also inspect already-loaded modules.
    for mod_name, mod in list(sys.modules.items()):
        if not mod_name.startswith("cek_surface"):
            continue
        src = getattr(mod, "__file__", None)
        if not src:
            continue
        try:
            names = imported_names(Path(src))
        except Exception:
            continue
        if "ux_channel" in names:
            hits.append(src)
    return hits


def second_cap_owners(registry: Any) -> list[str]:
    """On cek=require the only Cap machine on the registry is the adapter."""
    caps = getattr(registry, "_caps", None)
    owners: list[str] = []
    name = type(caps).__name__ if caps is not None else ""
    module = type(caps).__module__ if caps is not None else ""
    owners.append(f"{module}.{name}")
    return owners
