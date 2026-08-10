"""JSON helpers (wire dumps/loads) — no alias names."""

from __future__ import annotations

import os
import unittest

from ux_channel.wire import (
    available_engines,
    configure_wire,
    dumps,
    get_codec,
    loads,
    reset_wire,
    size_of,
)


class TestJsonHelpers(unittest.TestCase):
    def setUp(self):
        reset_wire()

    def tearDown(self):
        reset_wire()

    def test_auto_codec_known(self):
        c = get_codec()
        self.assertIn(c.name, available_engines())
        self.assertIn("stdlib", available_engines())

    def test_stdlib_roundtrip(self):
        configure_wire(engine="stdlib")
        self.assertEqual(get_codec().engine, "stdlib")
        self.assertEqual(loads(dumps({"a": 1, "b": [True, None]})), {"a": 1, "b": [True, None]})

    def test_size_of(self):
        configure_wire(engine="stdlib")
        self.assertEqual(size_of({"x": 1}), len(dumps({"x": 1}).encode("utf-8")))

    def test_unicode(self):
        configure_wire(engine="stdlib")
        self.assertEqual(loads(dumps({"m": "café 🎉"})), {"m": "café 🎉"})

    def test_unknown_engine_strict(self):
        with self.assertRaises((ValueError, RuntimeError)):
            configure_wire(engine="not-a-codec", strict=True)

    def test_env_engine(self):
        os.environ["UX_CHANNEL_WIRE_ENGINE"] = "stdlib"
        try:
            c = reset_wire()
            self.assertEqual(c.engine, "stdlib")
        finally:
            os.environ.pop("UX_CHANNEL_WIRE_ENGINE", None)
            reset_wire()

    def test_dumps_always_json_when_format_cxb(self):
        configure_wire(format="cxb")
        self.assertEqual(get_codec().format, "cxb")
        self.assertEqual(loads(dumps({"ok": True})), {"ok": True})


if __name__ == "__main__":
    unittest.main()
