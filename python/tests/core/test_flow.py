"""Flow layer — ch.on / ch.view / ch.ok / ch.err without losing command/island."""

from __future__ import annotations

from ux_channel import Channel, ChannelTest, Result

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_on_view_ok_flow():
    db = {"n": 0}
    ch = Channel.boot(secret=SECRET)

    @ch.region("Counter:root")
    def counter(ctx):
        return {"n": db["n"]}

    @counter.paint
    def counter_html(data, ctx):
        return f"<b>{data['n']}</b>"

    @ch.on("Counter.inc", refresh=["Counter:root"], auth=True)
    def inc(ctx):
        db["n"] += 1
        return ch.done("ok")

    ChannelTest(ch).call("Counter.inc").assert_fail("unauthorized")
    (
        ChannelTest(ch)
        .call("Counter.inc", user_id="u1")
        .assert_ok()
        .assert_morph("Counter:root", contains="1")
        .assert_notice("ok")
    )
    assert ch.html("Counter:root", wrap=False).find("1") >= 0


def test_ok_none_uses_decorator_toast():
    ch = Channel.boot(secret=SECRET)
    hits = {"n": 0}

    @ch.region("X:root")
    def x(ctx):
        return hits

    @x.paint
    def xh(data, ctx):
        return f"<i>{data['n']}</i>"

    @ch.on("X.touch", refresh=["X:root"], notice="touched")
    def touch():
        hits["n"] += 1
        # implicit ok via None

    ChannelTest(ch).call("X.touch").assert_ok().assert_notice("touched").assert_morph(
        "X:root", contains="1"
    )


def test_err_namespace():
    ch = Channel.boot(secret=SECRET)
    assert ch.fail.auth().error.code == "unauthorized"
    assert ch.fail.forbidden().error.code == "forbidden"

    @ch.region("F:root")
    def f(ctx):
        return {}

    @f.paint
    def fh(data, ctx):
        return "<form></form>"

    r = ch.fail.valid({"a": ["x"]}, region="F:root", html="<form></form>")
    assert not r.ok and r.error.code == "validation"


def test_command_and_on_coexist():
    ch = Channel.boot(secret=SECRET)

    @ch.on("A.x", refresh=[])
    def a():
        return Result.success()

    @ch.on("B.y")
    def b():
        return ch.done("y")

    ChannelTest(ch).call("A.x").assert_ok()
    ChannelTest(ch).call("B.y").assert_ok().assert_notice("y")
