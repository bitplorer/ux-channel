"""HTTP /action is JSON-only; health formats ≠ library codecs."""

from __future__ import annotations

from ux_channel.asgi.pipeline import health_payload, http_action_content_type_ok, preflight_action
from ux_channel.host.config import ChannelConfig
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.capability import CapService


SECRET = "http-surface-honesty-secret-32ch!!"


def test_http_action_content_type_json_or_form_only():
    assert http_action_content_type_ok(None) is True
    assert http_action_content_type_ok("application/json") is True
    assert http_action_content_type_ok("application/ux-channel+json; charset=utf-8") is True
    assert http_action_content_type_ok("application/x-www-form-urlencoded") is True
    assert http_action_content_type_ok("multipart/form-data; boundary=x") is True
    assert http_action_content_type_ok("application/ux-channel+cxb") is False
    assert http_action_content_type_ok("application/cbor") is False


def test_preflight_rejects_cxb():
    cfg = ChannelConfig.development(
        SECRET, require_channel_header=True, rate_limit_per_minute=0, cek="off"
    )
    fail = preflight_action(
        {
            "content-type": "application/ux-channel+cxb",
            "content-length": "4",
            "x-channel": "1",
        },
        config=cfg,
    )
    assert fail is not None
    result, status, _ = fail
    assert status == 400
    assert result.error is not None
    assert result.error.code == "bad_request"


def test_health_payload_formats_vs_codecs():
    reg = ActionRegistry(SECRET, require_cap=False)
    body = health_payload(reg, health_list=True, path="/ux-channel")
    assert body["formats"] == ["application/ux-channel+json"]
    assert "json" in body["codecs"]
    assert "cxb" in body["codecs"]
    assert "application/ux-channel+cxb" not in body["formats"]
    assert body["http"]["action"]["accept_response"] == ["application/ux-channel+json"]
    assert body["policy"]["present_cap_must_verify"] is True
    assert isinstance(body["policy"]["once_jti_enforced"], bool)
    assert type(reg._caps) is CapService
