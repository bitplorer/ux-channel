
"""Batch envelope HTTP status + meta details."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.transport.batch import dispatch_batch
from ux_channel.protocol.error_map import batch_http_status, enrich_batch_envelope
from ux_channel.protocol.types import Result


def _ch():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )

    @ch.on(name="T.ok")
    def ok():
        return ch.done(notice="y")

    @ch.on(name="T.bad")
    def bad():
        return Result.failure("validation", "no", fields={"f": ["x"]})

    @ch.on(name="T.auth", auth=True)
    def auth():
        return ch.done()

    return ch, app


def test_mixed_is_207():
    ch, app = _ch()
    cap_ok = ch.registry.mint("T.ok", {})
    cap_bad = ch.registry.mint("T.bad", {})
    out = dispatch_batch(
        ch.registry,
        [
            {"v": "1", "action": "T.ok", "args": {}, "cap": cap_ok},
            {"v": "1", "action": "T.bad", "args": {}, "cap": cap_bad},
        ],
    )
    assert out["meta"]["status_mode"] == "mixed"
    assert out["meta"]["http_status"] == 207
    assert out["meta"]["ok_count"] == 1
    assert out["meta"]["error_count"] == 1
    assert out["meta"]["item_statuses"] == [200, 422]
    assert batch_http_status(out) == 207

    client = TestClient(app)
    res = client.post(
        "/ux-channel/batch",
        json={
            "batch": [
                {"v": "1", "action": "T.ok", "args": {}, "cap": cap_ok},
                {"v": "1", "action": "T.bad", "args": {}, "cap": cap_bad},
            ]
        },
        headers={"X-Channel": "1", "Content-Type": "application/json"},
    )
    assert res.status_code == 207
    assert res.json()["meta"]["status_mode"] == "mixed"


def test_all_ok_200():
    ch, _ = _ch()
    cap = ch.registry.mint("T.ok", {})
    out = dispatch_batch(
        ch.registry, [{"v": "1", "action": "T.ok", "args": {}, "cap": cap}]
    )
    assert out["meta"]["http_status"] == 200
    assert out["meta"]["status_mode"] == "all_ok"


def test_all_error_worst_status():
    ch, _ = _ch()
    cap_bad = ch.registry.mint("T.bad", {})
    cap_auth = ch.registry.mint("T.auth", {})
    out = dispatch_batch(
        ch.registry,
        [
            {"v": "1", "action": "T.bad", "args": {}, "cap": cap_bad},
            {"v": "1", "action": "T.auth", "args": {}, "cap": cap_auth},
        ],
    )
    assert out["meta"]["status_mode"] == "all_error"
    # unauthorized 401 is worse than validation 422
    assert out["meta"]["http_status"] == 401
    assert out["meta"]["worst_code"] == "unauthorized"


def test_oversize_envelope_413():
    ch, _ = _ch()
    cap = ch.registry.mint("T.ok", {})
    items = [{"v": "1", "action": "T.ok", "args": {}, "cap": cap}] * 20
    out = dispatch_batch(ch.registry, items, max_items=2)
    assert out.get("error", {}).get("code") == "payload_too_large"
    assert out["meta"]["http_status"] == 413
    assert out["meta"]["status_mode"] == "envelope_error"


def test_empty_batch():
    out = enrich_batch_envelope({"v": "1", "ok": True, "batch": [], "ops": []})
    assert out["meta"]["http_status"] == 200
    assert out["meta"]["batch_size"] == 0
