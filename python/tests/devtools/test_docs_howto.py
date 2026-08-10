"""Docs hub integrity — ontological docs layout."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, toast
from ux_channel.host.catalog import action_catalog
from ux_channel.host.config import ChannelConfig

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

# (package, filename) — mirrors docs/ ontology
REQUIRED = [
    ("", "README.md"),
    ("", "index.md"),
    ("start", "HOW_TO.md"),
    ("start", "API.md"),
    ("start", "COOKBOOK.md"),
    ("start", "PRINCIPLES.md"),
    ("start", "GOLDEN_PATH.md"),
    ("start", "DESIGN.md"),
    ("start", "GLOSSARY.md"),
    ("start", "PATTERNS.md"),
    ("start", "API_SURFACE.md"),
    ("start", "LAYERS.md"),
    ("start", "FREEZE_0.1.md"),
    ("asgi", "FASTAPI.md"),
    ("asgi", "SSE.md"),
    ("asgi", "WEBSOCKET.md"),
    ("core", "RESULT.md"),
    ("core", "CLIENT_ERRORS.md"),
    ("dx", "INSPECTOR.md"),
    ("dx", "EXAMPLES.md"),
    ("bridges", "PLUGINS.md"),
    ("bridges", "NPM.md"),
    ("client", "INTEROP.md"),
    ("regions", "REGIONS.md"),
    ("regions", "COMPONENTS.md"),
    ("security", "SECURITY_AUDIT.md"),
    ("production", "PRODUCTION.md"),
    ("production", "ENTERPRISE.md"),
    ("foundations", "ARCHITECTURE.md"),
    ("foundations", "FOUNDATIONS.md"),
    ("agents", "AGENTS_MCP.md"),
]


def _path(pkg: str, name: str) -> Path:
    return DOCS / pkg / name if pkg else DOCS / name


def test_docs_hub_files_exist():
    for pkg, name in REQUIRED:
        p = _path(pkg, name)
        assert p.is_file(), f"{pkg}/{name}"
        assert p.stat().st_size > 80, f"{pkg}/{name}"
    assert (DOCS / "book" / "UX_CHANNEL_BOOK.md").is_file()
    # removed stale trees / redirects
    assert not (DOCS / "history").exists()
    assert not (DOCS / "USE_CASES.md").exists()
    assert not (DOCS / "PACKAGE.md").exists()
    assert not (DOCS / "MOAT.md").exists()
    assert not (DOCS / "GIANT_MOATS.md").exists()
    assert not (DOCS / "WIDGETS.md").exists()
    assert not (DOCS / "ISLANDS.md").exists()
    assert not (DOCS / "PLANES.md").exists()
    assert not (DOCS / "book" / "UX_CHANNEL_GUIDE.md").exists()


def test_howto_covers_core_topics():
    text = (DOCS / "start" / "HOW_TO.md").read_text()
    for needle in [
        "Install",
        "Channel.boot",
        "region",
        "control",
        "draft",
        "Intent",
        "Result",
        "FastAPI",
        "Security",
    ]:
        assert needle in text, needle


def test_fastapi_doc_lists_action_route():
    text = (DOCS / "asgi" / "FASTAPI.md").read_text()
    assert "/ux-channel/action" in text
    assert "Channel.boot" in text
    assert "X-UID-Channel" in text or "X-Channel" in text


def test_readme_points_to_howto():
    readme = (ROOT / "README.md").read_text()
    assert "docs/start/HOW_TO.md" in readme or "docs/HOW_TO.md" in readme or "HOW_TO" in readme
    assert "docs/README.md" in readme or "docs/index.md" in readme


def test_action_catalog():
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=False)

    @reg.action("Demo.ping")
    async def ping(n: int = 0):
        """Ping action."""
        return Result.success(toast("p"))

    cat = action_catalog(reg)
    assert cat[0]["name"] == "Demo.ping"
    assert cat[0]["async"] is True


def test_catalog_http_dev():
    cfg = ChannelConfig.development(
        secret="test-secret-key-32chars-minimum!!",
        enforce_same_origin=False,
        rate_limit_per_minute=0,
        health_list_actions=True,
    )
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)

    @reg.action("A")
    def a():
        return Result.success(toast("a"))

    from ux_channel.asgi.fastapi import mount_channel

    mount_channel(app, reg, config=cfg)
    c = TestClient(app)
    r = c.get("/ux-channel/catalog")
    assert r.status_code == 200
    assert any(x["name"] == "A" for x in r.json()["actions"])


def test_sse_doc_has_security_bottom_line():
    text = (DOCS / "asgi" / "SSE.md").read_text()
    assert "Bottom line" in text
    assert "Issue catalog" in text
    assert "Solutions matrix" in text
    assert "push_token" in text


def test_websocket_doc_has_security():
    text = (DOCS / "asgi" / "WEBSOCKET.md").read_text()
    assert "Bottom line" in text
    assert "sign_ws" in text or "sign_push" in text
    assert "/ux-channel/ws" in text
