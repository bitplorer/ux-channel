"""DX sharpening — mental model, doctor, media scaffold, CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.devtools.cli import main as cli_main
from ux_channel.scaffold import ScaffoldOptions, available_templates, create_app, validate_scaffold


def test_templates_include_media():
    assert "media" in available_templates()


def test_describe_and_doctor():
    mm = Channel.describe()
    assert "Public API" in mm and "media.plugin" in mm and "ux-dom" in mm
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        ),
    )
    doc = ch.doctor()
    assert doc["ok"] is True
    assert "hints" in doc and "diagnose" in doc
    assert "media" in doc["diagnose"]


def test_create_app_media_template():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "callapp"
        opts = ScaffoldOptions(app_name="callapp", dest=root, template="media", force=True)
        create_app(opts)
        assert (root / "app" / "main.py").is_file()
        text = (root / "app" / "main.py").read_text()
        assert "media.plugin" in text
        assert (root / ".ux_channel.json").is_file()
        meta = json.loads((root / ".ux_channel.json").read_text())
        assert meta["template"] == "media"
        report = validate_scaffold(root, template="media")
        assert report["ok"], report


def test_cli_dx_and_templates():
    assert cli_main(["templates"]) == 0
    assert cli_main(["dx"]) == 0


def test_cli_doctor():
    assert cli_main(["doctor"]) == 0
