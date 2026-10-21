"""A subject-bound Cap verifies only for the authenticated principal it names."""

from __future__ import annotations

from ux_channel import Channel, Intent, Result
from ux_channel.host.context import Principal

SECRET = "dev-cap-subject-principal-32chars!!"


def _channel() -> Channel:
    ch = Channel.boot(secret=SECRET)
    assert ch.registry._cek_require_owns_once(), "default boot is the cek-runtime Host"

    @ch.registry.action("Order.pay")
    def pay(order_id: str = "", subject: str = "", user_id: str = ""):
        return Result.success()

    return ch


def _pay(ch: Channel, args: dict, *, principal=None) -> Result:
    cap = ch.mint("Order.pay", args, sub="alice")
    return ch.registry.dispatch(
        Intent(action="Order.pay", args=args, cap=cap), principal=principal
    )


def test_subject_matches_authenticated_principal():
    for once in (False, True):
        ch = _channel()
        args = {"order_id": "o1"}
        cap = ch.mint("Order.pay", args, sub="alice", once=once)
        r = ch.registry.dispatch(
            Intent(action="Order.pay", args=args, cap=cap),
            principal=Principal.of("alice"),
        )
        assert r.ok, (once, r.error)


def test_subject_matches_auth_resolver_principal():
    ch = _channel()
    ch.registry.auth_resolver = lambda _request: Principal.of("alice")
    assert _pay(ch, {"order_id": "o1"}).ok


def test_other_principal_is_refused():
    ch = _channel()
    r = _pay(ch, {"order_id": "o1"}, principal=Principal.of("mallory"))
    assert not r.ok and r.error.code == "unauthorized"
    assert r.error.message == "subject bind mismatch"


def test_no_principal_fails_closed():
    ch = _channel()
    r = _pay(ch, {"order_id": "o1"})
    assert not r.ok and r.error.code == "unauthorized"


def test_subject_in_args_is_not_authentication():
    """Sealed args that name the subject do not stand in for a principal."""
    for key in ("subject", "user_id"):
        ch = _channel()
        r = _pay(ch, {"order_id": "o1", key: "alice"})
        assert not r.ok and r.error.code == "unauthorized", key
        assert "authenticated principal" in r.error.message, key


def test_cap_without_subject_needs_no_principal():
    ch = _channel()
    args = {"order_id": "o1"}
    cap = ch.mint("Order.pay", args)
    assert ch.registry.dispatch(Intent(action="Order.pay", args=args, cap=cap)).ok
    r = ch.registry.dispatch(
        Intent(action="Order.pay", args=args, cap=cap), principal=Principal.of("bob")
    )
    assert r.ok, r.error
