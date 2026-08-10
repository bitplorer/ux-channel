"""Regression: footguns similar to after-hook Result clobber."""

from ux_channel import Channel, Intent, Region

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_revalidate_skips_unknown_region_partial_ok():
    ch = Channel.boot(secret=SECRET)

    @ch.region("ok.r")
    def ok_r(ctx):
        return "hello"

    @ch.on(name="A.partial")
    def partial():
        return ch.done(refresh=["ok.r", "missing.r"], notice="partial")

    r = ch.registry.dispatch(
        Intent(action="A.partial", args={}, cap=ch.mint("A.partial", {}))
    )
    assert r.ok
    assert any(o.get("op") == "morph" and "hello" in str(o.get("html", "")) for o in r.ops)
    assert any(o.get("op") == "toast" for o in r.ops)


def test_revalidate_unknown_only_fails_with_notice_but_keeps_warning_toast():
    """Total paint failure is fail-closed; notice becomes warning toast on failed Result."""
    ch = Channel.boot(secret=SECRET)

    @ch.on(name="A.ghost")
    def ghost():
        return ch.done(refresh=["nope"], notice="only toast")

    r = ch.registry.dispatch(
        Intent(action="A.ghost", args={}, cap=ch.mint("A.ghost", {}))
    )
    assert not r.ok
    assert r.error and r.error.code == "render_error"
    assert any(o.get("op") == "toast" for o in r.ops)


def test_region_uid_overwrite_last_wins():
    ch = Channel.boot(secret=SECRET)

    @ch.region("same")
    def a(ctx):
        return "a"

    @ch.region("same")
    def b(ctx):
        return "b"

    assert "b" in ch.html("same", wrap=False)


def test_encode_result_shaped_dict():
    from ux_channel.encode import encode_result

    r = encode_result(
        {"ok": True, "ops": [{"op": "toast", "message": "x", "level": "info"}], "meta": {}},
        meta={"action": "T"},
    )
    assert r.ok
    assert r.ops and r.ops[0]["op"] == "toast"
    assert r.meta.get("action") == "T"


def test_sign_unknown_action_still_mints_but_validates_name():
    ch = Channel.boot(secret=SECRET)
    # does not raise — boot order may mint before register
    cap = ch.mint("Future.action", {"a": 1})
    assert isinstance(cap, str) and len(cap) > 10
