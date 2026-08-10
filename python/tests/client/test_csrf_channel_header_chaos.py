"""
CSRF channel header (X-Channel) × ux_dom control attrs × load/chaos.

Design under test
-----------------
* UxDom / ``ch.control(...).as_ux_dom()`` mint **cap + action attrs only**.
  They do **not** embed a CSRF token in HTML (by design).
* Browser client (``ux-channel.js``) always sends ``X-Channel: 1`` on
  JSON Intents; cross-site classic form posts cannot set that header easily.
* Server: ``require_channel_header`` gates JSON posts; form-urlencoded exempt
  for progressive enhance.
"""

from __future__ import annotations

import concurrent.futures
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.render.html import ControlAttrs
from ux_channel.security.security import channel_header_ok


SECRET = "csrf-chaos-test-secret-key-32bytes!!!"


def _boot(*, require_channel_header: bool = True, require_cap: bool = True):
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_channel_header=require_channel_header,
            require_cap=require_cap,
            rate_limit_per_minute=0,
            enforce_same_origin=False,
        ),
    )
    hits: list[str] = []

    @ch.on
    def add_line(sku: str = "") -> Any:
        hits.append(sku)
        return ch.done(notice=sku)

    return app, ch, hits


# ── unit: header policy ───────────────────────────────────────────────────


def test_channel_header_ok_values():
    assert channel_header_ok({"X-Channel": "1"}, required=True) is True
    assert channel_header_ok({"x-channel": "true"}, required=True) is True
    assert channel_header_ok({"X-Channel": "yes"}, required=True) is True
    assert channel_header_ok({"X-Channel": "0"}, required=True) is False
    assert channel_header_ok({}, required=True) is False
    assert channel_header_ok({}, required=False) is True
    # progressive enhance forms exempt
    assert (
        channel_header_ok(
            {},
            required=True,
            content_type="application/x-www-form-urlencoded",
        )
        is True
    )


# ── ux_dom attrs never carry CSRF ──────────────────────────────────────────


def test_control_as_ux_dom_has_no_csrf_token():
    app, ch, hits = _boot()
    attrs = ch.control("add_line", trust_sku="SKU-1")
    d = attrs.as_dict()
    u = attrs.as_ux_dom()
    assert "data-channel-cap" in d
    assert "data_channel_cap" in u
    assert "data-channel-action" in d
    # CSRF is not paint — tokens never appear on button data-channel-* attrs.
    # (Prefix "channel" in data-channel-* is intentional ownership provenance.)
    joined = " ".join(list(d.keys()) + list(u.keys())).lower()
    assert "csrf" not in joined
    assert isinstance(attrs, ControlAttrs) or hasattr(attrs, "as_ux_dom")


def test_ux_dom_button_attrs_work_only_with_header():
    """Simulate: render as_ux_dom → post Intent with cap; header is separate."""
    app, ch, hits = _boot()
    client = TestClient(app)
    ctrl = ch.control("add_line", trust_sku="A")
    ux_dom = ctrl.as_ux_dom()
    cap = ux_dom["data_channel_cap"]
    action = ux_dom["data_channel_action"]

    r_miss = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": action, "args": {"sku": "A"}, "cap": cap},
    )
    assert r_miss.status_code == 403
    body = r_miss.json()
    assert body.get("ok") is False
    assert "X-Channel" in str(body.get("error") or body)

    r_ok = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": action, "args": {"sku": "A"}, "cap": cap},
        headers={"X-Channel": "1"},
    )
    assert r_ok.status_code == 200
    assert r_ok.json().get("ok") is True
    assert hits == ["A"]


# ── chaos: concurrent good / bad mix ──────────────────────────────────────


def test_load_with_header_all_succeed():
    app, ch, hits = _boot()
    client = TestClient(app)
    # Cap binds trust args — use same sku every time (CSRF is under test)
    cap = ch.control("add_line", trust_sku="LOAD").as_dict()["data-channel-cap"]

    def one(i: int):
        r = client.post(
            "/ux-channel/action",
            json={
                "v": "1",
                "action": "add_line",
                "args": {"sku": "LOAD"},
                "cap": cap,
            },
            headers={"X-Channel": "1"},
        )
        return r.status_code, r.json().get("ok")

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(one, range(40)))
    assert all(s == 200 and ok for s, ok in results), results[:3]
    assert len(hits) == 40




def test_chaos_missing_header_never_succeeds():
    app, ch, hits = _boot()
    client = TestClient(app)
    cap = ch.control("add_line", trust_sku="X").as_dict()[
        "data-channel-cap"
    ]

    def one(i: int):
        # half missing, half wrong value
        headers = {} if i % 2 == 0 else {"X-Channel": "nope"}
        r = client.post(
            "/ux-channel/action",
            json={
                "v": "1",
                "action": "add_line",
                "args": {"sku": f"B{i}"},
                "cap": cap,
            },
            headers=headers,
        )
        return r.status_code, r.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(one, range(30)))
    for status, body in results:
        assert status == 403
        assert body.get("ok") is False
    assert hits == []


def test_chaos_mixed_traffic_header_is_hard_gate():
    """Good and bad traffic interleaved — only headered requests mutate."""
    app, ch, hits = _boot()
    client = TestClient(app)
    cap = ch.control("add_line", trust_sku="MIX").as_dict()["data-channel-cap"]

    def one(i: int):
        good = i % 3 != 0
        headers = {"X-Channel": "1"} if good else {}
        r = client.post(
            "/ux-channel/action",
            json={
                "v": "1",
                "action": "add_line",
                "args": {"sku": "MIX"},
                "cap": cap,
            },
            headers=headers,
        )
        return good, r.status_code, r.json().get("ok")

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(one, range(45)))
    good_ok = [r for r in results if r[0]]
    bad = [r for r in results if not r[0]]
    assert all(s == 200 and ok for _, s, ok in good_ok), good_ok[:2]
    assert all(s == 403 and not ok for _, s, ok in bad), bad[:2]
    assert len(hits) == len(good_ok)




def test_require_channel_header_off_allows_json_without_header():
    app, ch, hits = _boot(require_channel_header=False)
    client = TestClient(app)
    cap = ch.control("add_line", trust_sku="Z").as_dict()[
        "data-channel-cap"
    ]
    r = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "add_line", "args": {"sku": "Z"}, "cap": cap},
    )
    assert r.status_code == 200
    assert hits == ["Z"]


def test_js_source_always_sets_channel_header():
    """Guardrail: client runtime must hardcode X-Channel (ux_dom-independent)."""
    from pathlib import Path

    js = Path("src/ux_channel/static/ux-channel.js").read_text()
    assert "buildIntentHeaders" in js
    assert 'headers["X-Channel"] = "1"' in js or "headers['X-Channel'] = '1'" in js
    # set after app/framework merge so UxDom token cannot clear it
    assert js.index('headers["X-Channel"] = "1"') > js.index("__UX_CHANNEL_HEADERS")
