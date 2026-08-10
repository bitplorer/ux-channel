import pytest

from ux_channel import ActionRegistry, Result, morph, toast
from ux_channel.protocol.errors import ActionError
from ux_channel.security.limits import LimitExceeded, enforce_result_limits
from ux_channel.protocol.types import Intent


@pytest.fixture
def reg():
    return ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=False, expose_internal_errors=True)


@pytest.mark.asyncio
async def test_async_action(reg):
    @reg.action("Async.ping")
    async def ping(x: int = 1):
        return Result.success(toast(f"x={x}"))

    r = await reg.dispatch_async(Intent(action="Async.ping", args={"x": 2}))
    assert r.ok
    assert r.ops[0]["message"] == "x=2"


def test_hooks(reg):
    seen = []

    @reg.before
    def b(intent, args):
        seen.append("before")
        return None

    @reg.after
    def a(intent, result):
        seen.append("after")
        result.meta["hooked"] = True
        return result

    @reg.action("H.t")
    def t():
        return Result.success(toast("ok"))

    r = reg.dispatch(Intent(action="H.t"))
    assert seen == ["before", "after"]
    assert r.meta.get("hooked") is True


def test_before_short_circuit(reg):
    @reg.before
    def deny(intent, args):
        return Result.failure("unauthorized", "blocked")

    @reg.action("X")
    def x():
        return Result.success(toast("never"))

    r = reg.dispatch(Intent(action="X"))
    assert not r.ok
    assert r.error.code == "unauthorized"


def test_action_error(reg):
    @reg.action("V")
    def v():
        raise ActionError("validation", "bad", fields={"e": ["x"]})

    r = reg.dispatch(Intent(action="V"))
    assert not r.ok
    assert r.error.fields["e"] == ["x"]


def test_html_auto_target(reg):
    @reg.action("Html")
    def h():
        return '<div data-channel-id="box">hi</div>'

    r = reg.dispatch(Intent(action="Html"))
    assert r.ok
    assert r.ops[0]["op"] == "morph"
    assert r.ops[0]["target"] == '[data-channel-id="box"]'


def test_limits():
    huge = "x" * 1000
    r = Result.success(morph(target="#a", html=huge))
    with pytest.raises(LimitExceeded):
        enforce_result_limits(r, max_html_bytes=100)


def test_duplicate_register(reg):
    @reg.action("Dup")
    def a():
        return None

    with pytest.raises(ValueError):
        reg.register("Dup", lambda: None)


def test_go_navigate(reg):
    from ux_channel import Go

    @reg.action("GoHome")
    def g():
        return Go("/home")

    r = reg.dispatch(Intent(action="GoHome"))
    assert r.ops[0]["op"] == "navigate"
    assert r.ops[0]["href"] == "/home"


def test_int_coerce_from_form_string(reg):
    @reg.action("Add")
    def add(n: int):
        return Result.success(toast(str(n + 1)))

    r = reg.dispatch(Intent(action="Add", args={"n": "41"}))
    assert r.ok
    assert r.ops[0]["message"] == "42"
