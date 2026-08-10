import pytest

from ux_channel import ActionRegistry, Result, morph
from ux_channel.types import Intent


@pytest.fixture
def reg():
    r = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=True)

    @r.action("Counter.inc")
    def inc(n: int = 0) -> Result:
        return Result.success(
            morph(target='[data-channel-id="c"]', html=f'<div data-channel-id="c">{n + 1}</div>')
        )

    return r


def test_dispatch_with_cap(reg):
    args = {"n": 3}
    cap = reg.sign("Counter.inc", args)
    result = reg.dispatch(
        Intent(action="Counter.inc", args=args, cap=cap, request_id="t1")
    )
    assert result.ok
    assert result.ops[0]["op"] == "morph"
    assert "4" in result.ops[0]["html"]
    assert result.meta.get("action") == "Counter.inc"
    assert "duration_ms" in result.meta


def test_missing_cap(reg):
    result = reg.dispatch(Intent(action="Counter.inc", args={"n": 1}))
    assert not result.ok
    assert result.error and result.error.code == "unauthorized"


def test_unknown_action(reg):
    result = reg.dispatch(Intent(action="nope", cap=reg.sign("nope")))
    # cap signs any action string; dispatch still fails not_found
    assert not result.ok
    assert result.error.code == "not_found"


def test_bad_cap_args(reg):
    cap = reg.sign("Counter.inc", {"n": 1})
    result = reg.dispatch(Intent(action="Counter.inc", args={"n": 99}, cap=cap))
    assert not result.ok
    assert result.error.code == "unauthorized"
