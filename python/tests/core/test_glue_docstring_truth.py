"""The glue package docstring must match the real import edges.

ux_channel lazily imports ux_dom (render/html_safe.py, render/response.py).
ux_dom lazily imports ux_channel (ui/channel_bridge.py, cli/doctor.py).
A docstring that says neither imports the other misleads maintainers.
"""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"


def _imports_ux_dom(root: Path) -> list[str]:
    hits = []
    for rel in ("render/html_safe.py", "render/response.py"):
        path = root / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
            elif isinstance(node, ast.Import):
                mod = ",".join(a.name for a in node.names)
            if mod and any(p == "ux_dom" or p.startswith("ux_dom.") for p in mod.split(",")):
                hits.append(f"{path.relative_to(SRC)}:{node.lineno}")
    return hits


def test_docstring_does_not_claim_packages_are_independent():
    import ux_channel_ux_dom

    doc = ux_channel_ux_dom.__doc__ or ""
    assert _imports_ux_dom(SRC / "ux_channel"), "edge vanished; update this test"
    assert "Neither core package imports the other" not in doc


def test_docstring_names_the_soft_edges():
    import ux_channel_ux_dom

    doc = ux_channel_ux_dom.__doc__ or ""
    for name in ("render/html_safe.py", "render/response.py", "ui/channel_bridge.py"):
        assert name in doc, name
