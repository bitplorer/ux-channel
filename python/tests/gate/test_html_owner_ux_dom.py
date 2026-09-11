"""Soft 1 lock: HTML lower prefers ux-dom when present; no hard dep."""

from __future__ import annotations

from pathlib import Path

from ux_channel import ActionRegistry
from ux_channel.components import ChannelComponent, RegistryHost, to_html
from ux_channel.render.html_safe import _html_escape, _ux_dom_to_html
from ux_channel.render.morph_ir import elem, lower_html, region, text_node

ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = ROOT / "python" / "pyproject.toml"
SECRET = "soft1-html-owner-secret-key-32b!!!"


def _parse_poetry_deps(text: str) -> dict[str, str]:
    deps: dict[str, str] = {}
    in_deps = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_deps = line == "[tool.poetry.dependencies]"
            continue
        if not in_deps or "=" not in line or line.startswith("#"):
            continue
        name, _, rest = line.partition("=")
        deps[name.strip()] = rest.strip()
    return deps


def test_ux_dom_is_not_a_hard_dep():
    deps = _parse_poetry_deps(PYPROJECT.read_text(encoding="utf-8"))
    assert "ux-dom" not in deps
    assert "ux_dom" not in deps


def test_no_root_all_fashion_add_for_html_owner():
    import ux_channel

    assert "to_html" not in ux_channel.__all__
    assert "lower_html" not in ux_channel.__all__
    assert "_html_escape" not in ux_channel.__all__
    assert "_ux_dom_to_html" not in ux_channel.__all__


def test_lower_html_stdlib_escape_when_ux_dom_absent(monkeypatch):
    import ux_channel.render.html_safe as html_safe

    monkeypatch.setattr(html_safe, "_UX_ESCAPE", None)
    html = lower_html(text_node("<x>"))
    assert "&lt;x&gt;" in html


def test_lower_html_prefers_ux_dom_escape_when_present(monkeypatch):
    import ux_channel.render.html_safe as html_safe

    seen: list[str] = []

    def owner_escape(data, quote=True):
        seen.append(str(data))
        return f"OWN:{data}"

    monkeypatch.setattr(html_safe, "_UX_ESCAPE", owner_escape)
    assert lower_html(text_node("hi")) == "OWN:hi"
    assert seen == ["hi"]


def test_to_html_duck_type_when_ux_dom_absent(monkeypatch):
    import ux_channel.render.html_safe as html_safe

    monkeypatch.setattr(html_safe, "_UX_SERIALIZE", None)

    class UxDomish:
        def __render__(self):
            return "<em>u</em>"

    assert to_html(UxDomish()) == "<em>u</em>"
    assert to_html(None) == ""
    assert to_html("raw") == "raw"


def test_to_html_prefers_ux_dom_serialize_when_present(monkeypatch):
    import ux_channel.render.html_safe as html_safe

    class Tree:
        def __render__(self):
            return "<em>duck</em>"

    def is_html_renderable(value):
        return hasattr(value, "__render__")

    def to_html_bytes(value, *, encoding="utf-8"):
        assert value.__class__ is Tree
        return b"<em>owner</em>"

    monkeypatch.setattr(html_safe, "_UX_SERIALIZE", (is_html_renderable, to_html_bytes))
    assert to_html(Tree()) == "<em>owner</em>"


def test_to_html_no_second_stringify_of_owner_bytes(monkeypatch):
    import ux_channel.render.html_safe as html_safe

    class Tree:
        def __render__(self):
            raise AssertionError("duck-type must not run after owner serialize")

    monkeypatch.setattr(
        html_safe,
        "_UX_SERIALIZE",
        (lambda _v: True, lambda _v, *, encoding="utf-8": b"<b>once</b>"),
    )
    assert to_html(Tree()) == "<b>once</b>"


def test_channel_component_html_prefers_to_html(monkeypatch):
    import ux_channel.render.html_safe as html_safe

    class Tree:
        def __render__(self):
            return "<i>t</i>"

    monkeypatch.setattr(
        html_safe,
        "_UX_SERIALIZE",
        (lambda _v: True, lambda _v, *, encoding="utf-8": b"<i>owner</i>"),
    )

    class Box(ChannelComponent):
        kind = "Box"

        def render(self, **state):
            return Tree()

    host = RegistryHost(ActionRegistry(secret=SECRET, require_cap=True))
    box = Box(host, uid="Box:root")
    assert box.html() == "<i>owner</i>"


def test_region_lower_html_still_projects_ir():
    html = lower_html(region("cart", elem("span", "3 items", class_="n")))
    assert 'data-channel-id="cart"' in html
    assert "3 items" in html


def test_html_escape_stdlib_when_owner_absent(monkeypatch):
    import ux_channel.render.html_safe as html_safe

    monkeypatch.setattr(html_safe, "_UX_ESCAPE", None)
    assert "&lt;" in _html_escape("<z>")


def test_ux_dom_to_html_none_when_unloadable(monkeypatch):
    import ux_channel.render.html_safe as html_safe

    monkeypatch.setattr(html_safe, "_UX_SERIALIZE", None)
    assert _ux_dom_to_html(object()) is None
