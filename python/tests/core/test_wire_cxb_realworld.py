"""Real-world CXB battery — full-document fidelity, density, concurrency, live HTTP."""

from __future__ import annotations

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

from ux_channel import ops as O
from ux_channel.wire import decode, encode, reset_wire
from ux_channel.wire.cxb import decode_cxb, encode_cxb, is_cxb

# Import shared fixtures from the bench script
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "bench_cxb_realworld",
    Path(__file__).resolve().parents[2] / "scripts" / "bench_cxb_realworld.py",
)
_bench = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_bench)
FIXTURES = _bench.fixtures()


class TestRealworldRoundtrip(unittest.TestCase):
    def test_all_fixtures_cxb_roundtrip(self):
        for name, doc in FIXTURES.items():
            with self.subTest(name=name):
                raw = encode_cxb(doc)
                self.assertTrue(is_cxb(raw), name)
                out = decode_cxb(raw)
                if "ops" in doc:
                    self.assertEqual(len(out["ops"]), len(doc["ops"]), name)
                    for i, (a, b) in enumerate(zip(doc["ops"], out["ops"])):
                        self.assertEqual(a.get("op"), b.get("op"), f"{name} op[{i}]")
                        # full dict equality for library-built ops
                        self.assertEqual(a, b, f"{name} op[{i}] body")
                if "action" in doc:
                    self.assertEqual(out["action"], doc["action"])
                    self.assertEqual(out.get("args"), doc.get("args"))
                if "error" in doc:
                    self.assertEqual(out["error"]["code"], doc["error"]["code"])
                    self.assertEqual(out["error"].get("fields"), doc["error"].get("fields"))
                if "ok" in doc:
                    self.assertEqual(out["ok"], doc["ok"])

    def test_wire_encode_decode_all_formats(self):
        reset_wire()
        for name, doc in FIXTURES.items():
            for fmt in ("json", "msgpack", "cxb"):
                with self.subTest(name=name, fmt=fmt):
                    blob = encode(doc, format=fmt)
                    back = decode(blob.data, format=fmt)
                    if "ops" in doc:
                        self.assertEqual(len(back["ops"]), len(doc["ops"]))
                        self.assertEqual(back["ops"][0].get("op"), doc["ops"][0].get("op"))
                    if "action" in doc:
                        self.assertEqual(back["action"], doc["action"])


class TestRealworldDensity(unittest.TestCase):
    """CXB should not be pathologically larger than JSON on real Results."""

    def test_results_not_worse_than_json(self):
        for name, doc in FIXTURES.items():
            if "ops" not in doc:
                continue
            j = len(encode(doc, format="json").data)
            c = len(encode(doc, format="cxb").data)
            # allow tiny intents/results to be comparable; never 2× worse
            self.assertLessEqual(c, j * 2 + 64, f"{name}: cxb={c} json={j}")

    def test_bulk_and_cart_beat_json(self):
        for name in ("result_bulk_toasts", "result_cart_toast_morph", "result_multi_region_morph"):
            doc = FIXTURES[name]
            j = len(encode(doc, format="json").data)
            c = len(encode(doc, format="cxb").data)
            self.assertLess(c, j, f"{name} should be denser than JSON")


class TestRealworldConcurrency(unittest.TestCase):
    def test_parallel_all_fixtures(self):
        errors: list[str] = []

        def one(name: str, doc: dict):
            try:
                for _ in range(25):
                    out = decode_cxb(encode_cxb(doc))
                    if "ops" in doc:
                        assert len(out["ops"]) == len(doc["ops"])
                        assert out["ops"][0]["op"] == doc["ops"][0]["op"]
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}:{exc!r}")

        with ThreadPoolExecutor(max_workers=12) as pool:
            futs = [pool.submit(one, n, d) for n, d in FIXTURES.items() for _ in range(3)]
            for f in as_completed(futs):
                f.result()
        self.assertEqual(errors, [])

    def test_threads_mutating_shared_doc_safe(self):
        """Snapshot must isolate encode from concurrent list appends."""
        doc = {
            "v": "1",
            "ok": True,
            "ops": [O.toast("x", level="info")],
            "meta": {"n": 0},
        }
        stop = threading.Event()
        errors: list[str] = []

        def mutator():
            i = 0
            while not stop.is_set():
                doc["ops"].append(O.toast(f"m{i}", level="info"))
                doc["meta"]["n"] = i
                i += 1
                if len(doc["ops"]) > 200:
                    doc["ops"][:] = doc["ops"][:1]

        def encoder():
            try:
                for _ in range(100):
                    raw = encode_cxb(doc)
                    decode_cxb(raw)
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=mutator)] + [
            threading.Thread(target=encoder) for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads[1:]:
            t.join()
        stop.set()
        threads[0].join(timeout=1)
        self.assertEqual(errors, [])


class TestRealworldLiveAsgi(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_live_cart_and_dashboard_json_and_cxb(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from ux_channel import ChannelConfig, Result
        from ux_channel.asgi.fastapi import mount_channel
        from ux_channel.host.registry import ActionRegistry

        cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            rate_limit_per_minute=0,
        )
        app = FastAPI()
        reg = ActionRegistry.from_config(cfg)

        @reg.action("Shop.cart", idempotent=True)
        def cart():
            return Result.success(
                O.toast("Added to cart", level="success"),
                O.morph(
                    '[data-channel-id="cart"]',
                    '<div data-channel-id="cart"><b>2</b></div>',
                ),
            )

        @reg.action("Shop.dash", idempotent=True)
        def dash():
            return Result.success(
                O.morph(
                    '[data-channel-id="dashboard"]',
                    '<section data-channel-id="dashboard">ok</section>',
                ),
                O.bridge_update("chart", {"n": 1}),
            )

        mount_channel(app, reg, config=cfg)
        client = TestClient(app)

        for action, accept in (
            ("Shop.cart", None),
            ("Shop.cart", "application/ux-channel+cxb"),
            ("Shop.dash", None),
            ("Shop.dash", "application/ux-channel+cxb"),
        ):
            args: dict = {}
            cap = reg.mint(action, args)
            headers = {"X-Channel": "1"}
            if accept:
                headers["Accept"] = accept
            r = client.post(
                "/ux-channel/action",
                json={"v": "1", "action": action, "args": args, "cap": cap},
                headers=headers,
            )
            self.assertEqual(r.status_code, 200, r.text)
            if accept and "cxb" in accept:
                self.assertEqual(r.headers.get("x-channel-wire"), "cxb")
                body = decode_cxb(r.content)
            else:
                body = r.json()
            self.assertTrue(body["ok"])
            self.assertGreaterEqual(len(body["ops"]), 1)


if __name__ == "__main__":
    unittest.main()
