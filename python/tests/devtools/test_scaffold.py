"""Scaffold create-app — plug-and-play DX."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ux_channel.scaffold import (
    ScaffoldOptions,
    available_templates,
    create_app,
    validate_scaffold,
)


class TestScaffoldTemplates(unittest.TestCase):
    def test_template_list(self):
        t = available_templates()
        self.assertEqual(t, ["minimal", "live", "webrtc", "media", "full"])

    def test_each_template_creates_valid_tree(self):
        for name in available_templates():
            with self.subTest(template=name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td) / name
                    create_app(
                        ScaffoldOptions(
                            app_name=name,
                            dest=root,
                            template=name,
                            force=True,
                        )
                    )
                    report = validate_scaffold(root, template=name)
                    self.assertTrue(report["ok"], report)
                    main = (root / "app" / "main.py").read_text()
                    self.assertIn("Channel.boot", main)
                    self.assertIn("get_channel_config", main)
                    # compile
                    compile(main, "main.py", "exec")
                    cfg = (root / "app" / "config.py").read_text()
                    self.assertIn("ChannelConfig", cfg)

    def test_webrtc_template_has_media_hooks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "w"
            create_app(ScaffoldOptions(app_name="w", dest=root, template="webrtc"))
            main = (root / "app" / "main.py").read_text()
            # Elegant DX: ch.webrtc.page (embeds scripts + UxWebRTC panel)
            # Legacy raw template still has UxWebRTC/startMedia in _PAGE string.
            self.assertTrue(
                "webrtc.plugin" in main or "UxWebRTC" in main or "webrtc.session" in main,
                "expected plugin DX or raw UxWebRTC client",
            )
            self.assertTrue(
                "scripts_html" in main or "scripts(" in main or "UxWebRTC" in main,
                "scripts via plugin or ch.scripts",
            )

    def test_refuse_nonempty_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "x"
            root.mkdir()
            (root / "stale.txt").write_text("nope")
            with self.assertRaises(FileExistsError):
                create_app(ScaffoldOptions(app_name="x", dest=root, template="minimal"))

    def test_cli_create_app(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "cliapp"
            r = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ux_channel",
                    "create-app",
                    "cliapp",
                    "--dir",
                    str(dest),
                    "-t",
                    "minimal",
                    "--force",
                ],
                capture_output=True,
                text=True,
                cwd=td,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue((dest / "app" / "main.py").is_file())


if __name__ == "__main__":
    unittest.main()
