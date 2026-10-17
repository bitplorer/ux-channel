"""Bloat guard: no module imports a name it never uses (stdlib-only, no ruff needed).

Package ``__init__.py`` files are skipped: they re-export. A name listed in a
module's ``__all__`` counts as used. ``from __future__`` imports and imports
marked ``# noqa`` (deliberate re-exports) are ignored.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN = ("src",)


def _unused(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    imported: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and "noqa" in lines[node.lineno - 1]:
            continue
        if isinstance(node, ast.Import):
            for a in node.names:
                imported[(a.asname or a.name).split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            for a in node.names:
                if a.name != "*":
                    imported[a.asname or a.name] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            used |= {
                e.value for e in getattr(node.value, "elts", ()) if isinstance(e, ast.Constant)
            }
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # string annotations ("Foo | None") reference names too
            used |= set(node.value.replace("[", " ").replace("]", " ").replace("|", " ").replace(",", " ").replace(".", " ").split())
    return [f"{path.relative_to(ROOT)}:{line} {name}" for name, line in imported.items() if name not in used]


class NoUnusedImports(unittest.TestCase):
    def test_no_unused_imports(self):
        hits = []
        for rel in SCAN:
            for py in sorted((ROOT / rel).rglob("*.py")):
                if py.name == "__init__.py":
                    continue
                hits += _unused(py)
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
