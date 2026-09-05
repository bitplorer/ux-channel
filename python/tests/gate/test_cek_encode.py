"""Cut #2 encoding maps — Channel nouns → frozen CEK nouns.

No cek_host import required. Manifest/stamp never grant Cap.
flow_id is correlation only (ADR 0007 / LAW §10 trace).
"""

from __future__ import annotations

from ux_channel.cek.encode import (
    FROZEN_CEK_NOUNS,
    flow_id_to_trace,
    hello_to_manifest,
    hello_to_profile,
    intent_trace,
    manifest_grants_cap,
    stamp_to_handshake,
)


def test_frozen_cek_nouns_are_the_charter_set():
    assert "Cap" in FROZEN_CEK_NOUNS
    assert "Intent" in FROZEN_CEK_NOUNS
    assert "Result" in FROZEN_CEK_NOUNS
    assert "Op" in FROZEN_CEK_NOUNS
    assert "Profile" in FROZEN_CEK_NOUNS
    assert "Manifest" in FROZEN_CEK_NOUNS
    assert "Trace" in FROZEN_CEK_NOUNS
    # Do not invent nouns.
    assert "FlowEngine" not in FROZEN_CEK_NOUNS
    assert "EffectGraph" not in FROZEN_CEK_NOUNS


def test_flow_id_maps_to_trace_correlation_only():
    assert flow_id_to_trace("flow_abc") == "flow_abc"
    assert flow_id_to_trace("") is None
    assert flow_id_to_trace(None) is None
    tr = flow_id_to_trace("flow_abc")
    # Encoding is a string id — never a Cap object / token shape.
    assert isinstance(tr, str)
    assert "." not in tr or not tr.split(".", 1)[-1].isalnum() or len(tr) < 80


def test_intent_trace_prefers_explicit_trace_then_flow_id():
    assert intent_trace(meta={"trace": "t-1"}, args={"flow_id": "flow_x"}) == "t-1"
    assert intent_trace(meta={"flow_id": "flow_y"}, args={}) == "flow_y"
    assert intent_trace(meta={}, args={"flow_id": "flow_z"}) == "flow_z"
    assert intent_trace(meta={}, args={}) is None


def test_hello_to_profile_is_handshake_not_cap():
    hello = {"profiles": ["web.v1"], "features": ["seq", "invoke"]}
    profile = hello_to_profile(hello)
    assert profile["name"] == "web.v1"
    assert "apply_set" in profile
    assert "cap" not in profile
    assert "sig" not in profile
    assert profile.get("unknown_op_policy") in ("skip", "fail_batch")


def test_hello_to_manifest_never_grants_cap():
    hello = {"profiles": ["web.v1", "agent.v1"], "features": ["seq"]}
    manifest = hello_to_manifest(hello)
    assert "law_generation" in manifest
    assert "web.v1" in manifest["profiles"]
    assert "cap" not in manifest
    assert manifest_grants_cap(manifest) is False
    # Handshake only — no authority fields.
    for banned in ("cap", "token", "secret", "sig", "jti"):
        assert banned not in manifest


def test_stamp_encoding_is_not_a_cap():
    enc = stamp_to_handshake("st_1", {"call", "ping"}, kind="invoke")
    assert enc["stamp_id"] == "st_1"
    assert set(enc["methods"]) == {"call", "ping"}
    assert enc["kind"] == "invoke"
    assert enc.get("authority") != "cap"
    assert "cap" not in enc
    assert enc.get("not_cap") is True
