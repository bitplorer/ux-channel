
"""Chaos: every ERROR_HTTP_STATUS code + wire-shape footguns."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result
from ux_channel.batch import dispatch_batch, item_is_retryable
from ux_channel.encode import encode_result
from ux_channel.error_map import (
    ERROR_HTTP_STATUS,
    catalog,
    ensure_error_meta,
    http_status_for,
    kind_for_code,
    should_retry,
)


SECRET = "dev-secret-key-32chars-minimum!!!!"


def _boot():
    app = FastAPI()
    ch = Channel.boot(app, config=ChannelConfig.development(secret=SECRET))
    for code in ERROR_HTTP_STATUS:

        def make(c=code):
            @ch.on(name=f"Z.{c}")
            def h(c=c):
                kw = {}
                if c == "rate_limited":
                    kw["retryable"] = True
                    kw["retry_after"] = 2
                if c == "validation":
                    kw["fields"] = {"f": ["x"]}
                return Result.failure(c, f"m-{c}", **kw)

            return h

        make()

    @ch.on(name="Z.ok")
    def ok():
        return ch.done()

    return ch, app


def test_catalog_aligned_with_should_retry():
    for row in catalog():
        assert row["http_status"] == ERROR_HTTP_STATUS[row["code"]]
        assert row["retryable_default"] == should_retry(row["code"])
        assert row["kind"] == kind_for_code(row["code"])
    assert should_retry("internal") is False


def test_every_code_http_and_batch():
    ch, app = _boot()
    client = TestClient(app)
    for code, status in ERROR_HTTP_STATUS.items():
        cap = ch.registry.sign(f"Z.{code}", {})
        res = client.post(
            "/ux-channel/action",
            json={"v": "1", "action": f"Z.{code}", "args": {}, "cap": cap},
            headers={"X-Channel": "1", "Content-Type": "application/json"},
        )
        assert res.status_code == status, code
        body = res.json()
        assert body["ok"] is False
        assert body["error"]["code"] == code
        assert body["meta"]["error_kind"] == kind_for_code(code)
        if status == 429:
            assert res.headers.get("Retry-After")

        out = dispatch_batch(
            ch.registry,
            [{"v": "1", "action": f"Z.{code}", "args": {}, "cap": cap}],
        )
        assert out["meta"]["http_status"] == status
        assert out["meta"]["worst_code"] == code
        assert out["meta"]["status_mode"] == "all_error"


def test_mixed_batch_207():
    ch, _ = _boot()
    items = [
        {
            "v": "1",
            "action": "Z.ok",
            "args": {},
            "cap": ch.registry.sign("Z.ok", {}),
        }
    ]
    for code in list(ERROR_HTTP_STATUS)[:5]:
        items.append(
            {
                "v": "1",
                "action": f"Z.{code}",
                "args": {},
                "cap": ch.registry.sign(f"Z.{code}", {}),
            }
        )
    out = dispatch_batch(ch.registry, items, max_items=32)
    assert out["meta"]["status_mode"] == "mixed"
    assert out["meta"]["http_status"] == 207


def test_result_shaped_dict_not_swallowed():
    """Regression: {"ok": false, "error": ...} was coerced to empty ok Result."""
    ch, app = _boot()

    @ch.on(name="Z.wire")
    def wire():
        return {"ok": False, "error": {"code": "validation", "message": "wire"}}

    r = encode_result({"ok": False, "error": {"code": "validation", "message": "x"}})
    assert r.ok is False
    assert r.error and r.error.code == "validation"

    client = TestClient(app)
    res = client.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "Z.wire",
            "args": {},
            "cap": ch.registry.sign("Z.wire", {}),
        },
        headers={"X-Channel": "1", "Content-Type": "application/json"},
    )
    assert res.status_code == 422
    assert res.json()["ok"] is False
    assert res.json()["error"]["code"] == "validation"


def test_item_is_retryable_matrix_all_codes():
    for code in ERROR_HTTP_STATUS:
        r = Result.failure(code, "m")
        r.error.retryable = None  # type: ignore[union-attr]
        assert item_is_retryable(r) == should_retry(code), code


def test_toast_config_mapping_still_works():
    ch, app = _boot()

    @ch.on(name="Z.toastcfg")
    def tcfg():
        return {"toast": "hello", "toast_level": "info"}

    client = TestClient(app)
    res = client.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "Z.toastcfg",
            "args": {},
            "cap": ch.registry.sign("Z.toastcfg", {}),
        },
        headers={"X-Channel": "1", "Content-Type": "application/json"},
    )
    assert res.status_code == 200
    assert any(o.get("op") == "toast" for o in res.json()["ops"])
