#!/usr/bin/env python3
"""Enforce LONGEVITY.md separation: strata, root surface, no eager L4 in core.

  python3 scripts/check_longevity.py
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "python" / "src" / "ux_channel"
MAP = PKG / "PACKAGE_MAP.json"

# Core packages must not eagerly import these at module top level
L4_PLANES = (
    "agent_runtime",
    "mcp",
    "workplace",
    "bridge",
    "bridges",
    "realtime",
    "components",
    "io_adapters",
)
CORE = ("protocol", "host", "render", "security", "api")


def _top_level_imports(path: Path) -> list[str]:
    """Return module names imported at top level (not inside functions)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"SYNTAX:{exc}"]
    found: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.append(node.module)
            else:
                found.append(".")
        elif isinstance(node, ast.If):
            # skip TYPE_CHECKING blocks loosely — still scan non-TYPE_CHECKING
            test = node.test
            skip = False
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                skip = True
            if not skip:
                for sub in node.body:
                    if isinstance(sub, ast.ImportFrom) and sub.module:
                        found.append(sub.module)
                    elif isinstance(sub, ast.Import):
                        for alias in sub.names:
                            found.append(alias.name)
    return found


def check() -> list[str]:
    problems: list[str] = []
    meta = json.loads(MAP.read_text(encoding="utf-8"))
    strata = meta.get("strata") or {}
    if not strata:
        problems.append("PACKAGE_MAP.json missing strata map")
        return problems

    for pkg, level in strata.items():
        if level not in {"L1", "L2", "L3", "L4", "L5"}:
            problems.append(f"unknown stratum {level!r} for {pkg}")
        if not (PKG / pkg).is_dir():
            problems.append(f"strata package missing on disk: {pkg}")

    # every product/cohesive package should be stratified
    packages = set((meta.get("packages") or {}).keys())
    for pkg in packages:
        if pkg not in strata:
            problems.append(f"package {pkg} has no strata entry")

    # root only application — no L4 names
    sys.path.insert(0, str(ROOT / "python" / "src"))
    import ux_channel as u

    # Import-weight: root must not load agent kernel runner or devtools.trace eagerly
    heavy = (
        "ux_channel.agent_runtime.runner",
        "ux_channel.agent_runtime.tools",
        "ux_channel.agent_runtime.peer",
        "ux_channel.devtools.trace",
        "ux_channel.devtools.agents_api",
        "ux_channel.devtools.forensics",
        "ux_channel.devtools.intent_log",
        "ux_channel.realtime",
        "ux_channel.mcp",
        "ux_channel.wire",
        "ux_channel.wire.cxb",
        "ux_channel.protocol.serde",
        "ux_channel.protocol.encode",
        "ux_channel.render.renderers",
        "ux_channel.host.state_api",
    )
    for mod in heavy:
        if mod in sys.modules:
            problems.append(f"eager heavy import after ux_channel load: {mod}")

    for plane in L4_PLANES:
        if plane in getattr(u, "__all__", ()):
            problems.append(f"root __all__ must not include L4 plane {plane}")
        # bound as submodule via package namespace is OK (ux_channel.bridge after import)
        # but must not re-export plane public API names that are not packages

    power_forbidden_on_root = (
        "MemoryStateStore",
        "ChannelTest",
        "AgentRunner",
        "McpToolAdapter",
        "RedisStateStore",
    )
    for name in power_forbidden_on_root:
        if name in u.__all__:
            problems.append(f"root __all__ must not include power name {name}")
        if hasattr(u, name) and name not in {"bridge"}:  # packages may appear after import
            # only fail if it's not a module (re-exported class/fn)
            obj = getattr(u, name)
            if not hasattr(obj, "__path__"):
                problems.append(f"root must not bind power symbol {name}")

    # core packages: no eager top-level imports of L4
    for core in CORE:
        d = PKG / core
        if not d.is_dir():
            continue
        for path in d.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            imports = _top_level_imports(path)
            for imp in imports:
                for plane in L4_PLANES:
                    if imp == f"ux_channel.{plane}" or imp.startswith(f"ux_channel.{plane}."):
                        # allow TYPE_CHECKING only — already skipped somewhat
                        problems.append(
                            f"eager L4 import in core {path.relative_to(PKG)}: {imp}"
                        )

    # longevity doc present
    if not (ROOT / "LONGEVITY.md").is_file():
        problems.append("missing LONGEVITY.md")

    return problems


def main() -> int:
    problems = check()
    if problems:
        print(f"longevity: {len(problems)} issue(s)", file=sys.stderr)
        for p in problems:
            print(" -", p, file=sys.stderr)
        return 1
    print("longevity: OK (strata + root surface + core/L4 boundary)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
