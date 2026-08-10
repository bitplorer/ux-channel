
"""Batch error code → status aggregation."""

from __future__ import annotations

from ux_channel import Channel, ChannelConfig
from ux_channel.batch import dispatch_batch
from ux_channel.error_map import (
    ERROR_HTTP_STATUS,
    batch_http_status,
    map_batch_error_codes,
)
from ux_channel.types import Result
from fastapi import FastAPI


def _ch():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )

    @ch.on(name="M.ok")
    def ok():
        return ch.done()

    @ch.on(name="M.val")
    def val():
        return Result.failure("validation", "v")

    @ch.on(name="M.auth", auth=True)
    def auth():
        return ch.done()

    @ch.on(name="M.rate")
    def rate():
        return Result.failure("rate_limited", "slow", retryable=True)

    return ch


def test_code_counts_and_code_http():
    ch = _ch()
    caps = {
        "ok": ch.registry.sign("M.ok", {}),
        "val": ch.registry.sign("M.val", {}),
        "auth": ch.registry.sign("M.auth", {}),
        "rate": ch.registry.sign("M.rate", {}),
    }
    out = dispatch_batch(
        ch.registry,
        [
            {"v": "1", "action": "M.ok", "args": {}, "cap": caps["ok"]},
            {"v": "1", "action": "M.val", "args": {}, "cap": caps["val"]},
            {"v": "1", "action": "M.auth", "args": {}, "cap": caps["auth"]},
            {"v": "1", "action": "M.rate", "args": {}, "cap": caps["rate"]},
        ],
    )
    m = out["meta"]
    assert m["status_mode"] == "mixed"
    assert m["http_status"] == 207
    assert m["item_codes"][0] is None
    assert m["code_counts"]["validation"] == 1
    assert m["code_counts"]["unauthorized"] == 1
    assert m["code_counts"]["rate_limited"] == 1
    assert m["kind_counts"]["validation"] == 1
    assert m["kind_counts"]["auth"] == 1
    assert m["kind_counts"]["network"] == 1
    assert m["code_http"]["validation"] == 422
    assert m["code_http"]["unauthorized"] == 401
    assert m["code_http"]["rate_limited"] == 429
    # worst among failures by severity — rate 429 beats 401 and 422
    assert m["worst_code"] == "rate_limited"
    assert m["worst_kind"] == "network"


def test_all_error_maps_worst_to_http():
    ch = _ch()
    out = dispatch_batch(
        ch.registry,
        [
            {
                "v": "1",
                "action": "M.val",
                "args": {},
                "cap": ch.registry.sign("M.val", {}),
            },
            {
                "v": "1",
                "action": "M.auth",
                "args": {},
                "cap": ch.registry.sign("M.auth", {}),
            },
        ],
    )
    m = out["meta"]
    assert m["status_mode"] == "all_error"
    assert m["worst_code"] == "unauthorized"
    assert m["http_status"] == ERROR_HTTP_STATUS["unauthorized"]
    assert batch_http_status(out) == m["http_status"]


def test_map_batch_error_codes_helper():
    ch = _ch()
    out = dispatch_batch(
        ch.registry,
        [
            {
                "v": "1",
                "action": "M.val",
                "args": {},
                "cap": ch.registry.sign("M.val", {}),
            }
        ],
    )
    s = map_batch_error_codes(out)
    assert s["worst_code"] == "validation"
    assert s["code_counts"] == {"validation": 1}
    assert s["http_status"] == 422


def test_every_catalog_code_has_stable_batch_http():
    """Each canonical code alone in a failure envelope maps to its HTTP status."""
    for code, status in ERROR_HTTP_STATUS.items():
        env = {
            "v": "1",
            "ok": False,
            "batch": [
                {
                    "ok": False,
                    "ops": [],
                    "error": {"code": code, "message": code},
                }
            ],
        }
        from ux_channel.error_map import enrich_batch_envelope

        e = enrich_batch_envelope(env)
        assert e["meta"]["http_status"] == status, code
        assert e["meta"]["worst_code"] == code
        assert e["meta"]["code_http"][code] == status
