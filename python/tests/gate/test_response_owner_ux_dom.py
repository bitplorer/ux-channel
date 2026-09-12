"""Soft 4 lock: render/response.py prefers ux_dom.response; no hard dep."""

from __future__ import annotations

from pathlib import Path

import ux_channel
from ux_channel.render.response import HTMLResponse, render_content

ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = ROOT / "python" / "pyproject.toml"
RESPONSE = ROOT / "python" / "src" / "ux_channel" / "render" / "response.py"
ASGI_FASTAPI = ROOT / "python" / "src" / "ux_channel" / "asgi" / "fastapi.py"


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


def test_no_root_all_fashion_add_for_response_owner():
    assert "HTMLResponse" not in ux_channel.__all__
    assert "html_response" not in ux_channel.__all__
    assert "render_content" not in ux_channel.__all__


def test_response_module_names_ux_dom_response_owner():
    src = RESPONSE.read_text(encoding="utf-8")
    assert "ux_dom.response" in src
    lowered = src.replace("**", "").replace("``", "")
    assert "does not own response HTML helpers" in lowered


def test_keep_mount_channel_and_asgi_cap_door():
    from ux_channel.asgi import mount_channel

    assert callable(mount_channel)
    assert ASGI_FASTAPI.is_file(), "KEEP: do not gut asgi/fastapi.py"


def test_render_content_leftover_when_ux_dom_absent(monkeypatch):
    import ux_channel.render.response as response

    monkeypatch.setattr(response, "_UX_RESPONSE", None)

    class Tree:
        def __render__(self):
            return "<em>u</em>"

    class Markup:
        def __html__(self):
            return "<b>s</b>"

    class Regionish:
        uid = "cart"

        def html(self):
            return "<span>3</span>"

    assert render_content(Tree()) == "<em>u</em>"
    assert render_content(Markup()) == "<b>s</b>"
    assert render_content(Regionish()) == "<span>3</span>"
    assert render_content(None) == ""
    assert render_content("raw") == "raw"
    assert render_content(b"bytes") == "bytes"


def test_render_content_prefers_ux_dom_response_when_present(monkeypatch):
    import ux_channel.render.response as response

    class Tree:
        def __render__(self):
            return "<em>duck</em>"

    def is_html_renderable(value):
        return hasattr(value, "__render__")

    def to_html_bytes(value, *, encoding="utf-8"):
        assert value.__class__ is Tree
        return b"<em>owner</em>"

    monkeypatch.setattr(response, "_UX_RESPONSE", (is_html_renderable, to_html_bytes))
    assert render_content(Tree()) == "<em>owner</em>"


def test_render_content_no_second_stringify_of_owner_bytes(monkeypatch):
    import ux_channel.render.response as response

    class Tree:
        def __render__(self):
            raise AssertionError("duck-type must not run after owner serialize")

    monkeypatch.setattr(
        response,
        "_UX_RESPONSE",
        (lambda _v: True, lambda _v, *, encoding="utf-8": b"<b>once</b>"),
    )
    assert render_content(Tree()) == "<b>once</b>"


def test_html_response_uses_owner_prepare_when_present(monkeypatch):
    import ux_channel.render.response as response

    if HTMLResponse is None:
        return

    class Tree:
        def __render__(self):
            raise AssertionError("leftover __render__ must not run after owner")

    monkeypatch.setattr(
        response,
        "_UX_RESPONSE",
        (lambda _v: True, lambda _v, *, encoding="utf-8": b"<i>owner</i>"),
    )
    out = HTMLResponse(Tree())
    assert out.body == b"<i>owner</i>"
    assert out.media_type == "text/html"
