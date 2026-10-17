"""Unreachable or no-op code removed in the 0.1.2 cleanup stays gone."""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "ux_channel"


def _func(path: Path, name: str) -> ast.AST:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def _always_exits(stmt: ast.stmt) -> bool:
    if isinstance(stmt, (ast.Return, ast.Raise)):
        return True
    if isinstance(stmt, ast.Try):
        body = stmt.finalbody and any(_always_exits(s) for s in stmt.finalbody)
        return bool(body) or (
            any(_always_exits(s) for s in stmt.body)
            and all(any(_always_exits(s) for s in h.body) for h in stmt.handlers)
        )
    return False


def _unreachable(fn: ast.AST) -> list[int]:
    out: list[int] = []
    for node in ast.walk(fn):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            for i, stmt in enumerate(block[:-1]):
                if _always_exits(stmt):
                    out.append(block[i + 1].lineno)
                    break
        if isinstance(node, ast.Try) and node.orelse and any(_always_exits(s) for s in node.body):
            out.append(node.orelse[0].lineno)
    return out


def test_registry_dispatch_has_no_unreachable_code():
    assert _unreachable(_func(SRC / "host" / "registry.py", "dispatch")) == []


def test_push_security_has_no_unreachable_code():
    tree = ast.parse((SRC / "security" / "push_security.py").read_text(encoding="utf-8"))
    hits = [ln for fn in ast.walk(tree) if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) for ln in _unreachable(fn)]
    assert hits == []


def test_enterprise_has_no_if_false_assignment():
    assert "if False else" not in (SRC / "devtools" / "enterprise.py").read_text(encoding="utf-8")
