"""create-app smoke in the gate — generated app compiles and is production-shaped."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ux_channel.scaffold import ScaffoldOptions, create_app, validate_scaffold


def test_create_app_minimal_compiles_and_teaches():
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "stier"
        root = create_app(ScaffoldOptions(app_name="stier", dest=dest, template="minimal"))
        report = validate_scaffold(root, template="minimal")
        assert report["ok"], report.get("errors")
        main = (root / "app" / "main.py").read_text(encoding="utf-8")
        assert "Channel.boot" in main
        assert "@ch.region" in main
        assert "@ch.on" in main
        readme = (root / "README.md").read_text(encoding="utf-8")
        assert "doctor" in readme.lower()
        assert "upgrade-check" in readme
        cfg = (root / "app" / "config.py").read_text(encoding="utf-8")
        assert "require_cap=False" not in cfg
        assert "ChannelConfig.production" in cfg


def test_create_app_prod_template_keeps_require_cap():
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "prodapp"
        root = create_app(ScaffoldOptions(app_name="prodapp", dest=dest, template="minimal"))
        cfg = (root / "app" / "config.py").read_text(encoding="utf-8")
        assert "require_cap=False" not in cfg
        # production factory is the deploy path
        assert "ChannelConfig.production" in cfg
