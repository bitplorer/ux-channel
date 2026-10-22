"""A subject-bound Cap verifies only for the authenticated principal it names.

The rule is the same on the cek-runtime Host and on classic CapService
(``cek="off"``), with or without ``bind_cap_to_principal``.
"""

from __future__ import annotations

import pytest

from ux_channel import Channel, ChannelConfig, Intent, Result
from ux_channel.host.context import Principal

SECRET = "dev-cap-subject-principal-32chars!!"

HOSTS = pytest.mark.parametrize(
    "cek,bind",
    [("require", False), ("off", False), ("off", True)],
    ids=["cek", "classic", "classic-bind"],
)


def _channel(cek: str, bind: bool) -> Channel:
    cfg = ChannelConfig.development(
        secret=SECRET, cek=cek, bind_cap_to_principal=bind
    )
    ch = Channel.boot(config=cfg)
    assert ch.registry._cek_require_owns_once() == (cek == "require")
    ch.seen = []

    @ch.registry.action("Order.pay")
    def pay(ctx, order_id: str = "", subject: str = "", user_id: str = ""):
        ch.seen.append(ctx.principal.id if ctx.principal else None)
        return Result.success()

    return ch


def _pay(ch: Channel, args: dict, *, principal=None) -> Result:
    cap = ch.mint("Order.pay", args, sub="alice")
    return ch.registry.dispatch(
        Intent(action="Order.pay", args=args, cap=cap), principal=principal
    )


def _refused(ch: Channel, r: Result) -> bool:
    return not r.ok and r.error.code == "unauthorized" and ch.seen == []


@HOSTS
def test_subject_matches_authenticated_principal(cek, bind):
    for once in (False, True):
        ch = _channel(cek, bind)
        args = {"order_id": "o1"}
        cap = ch.mint("Order.pay", args, sub="alice", once=once)
        r = ch.registry.dispatch(
            Intent(action="Order.pay", args=args, cap=cap),
            principal=Principal.of("alice"),
        )
        assert r.ok, (once, r.error)
        assert ch.seen == ["alice"]


@HOSTS
def test_subject_matches_auth_resolver_principal(cek, bind):
    ch = _channel(cek, bind)
    ch.registry.auth_resolver = lambda _request: Principal.of("alice")
    assert _pay(ch, {"order_id": "o1"}).ok
    assert ch.seen == ["alice"]


@HOSTS
def test_other_principal_is_refused(cek, bind):
    ch = _channel(cek, bind)
    r = _pay(ch, {"order_id": "o1"}, principal=Principal.of("mallory"))
    assert _refused(ch, r), r.error
    assert "mismatch" in r.error.message


@HOSTS
def test_empty_subject_matches_no_principal(cek, bind):
    """An empty Cap subject names nobody, not the empty principal id."""
    ch = _channel(cek, bind)
    args = {"order_id": "o1"}
    cap = ch.mint("Order.pay", args, sub="")
    for principal in (Principal.of(""), Principal.of("alice"), None):
        r = ch.registry.dispatch(
            Intent(action="Order.pay", args=args, cap=cap), principal=principal
        )
        assert _refused(ch, r), (principal, r.error)


@HOSTS
def test_no_principal_fails_closed(cek, bind):
    """The Cap subject never stands in for a missing principal."""
    ch = _channel(cek, bind)
    assert _refused(ch, _pay(ch, {"order_id": "o1"}))


@HOSTS
def test_subject_in_args_is_not_authentication(cek, bind):
    """Sealed args that name the subject do not stand in for a principal."""
    for key in ("subject", "user_id", "sub"):
        ch = _channel(cek, bind)
        r = _pay(ch, {"order_id": "o1", key: "alice"})
        assert _refused(ch, r), (key, r.error)
        assert "authenticated principal" in r.error.message, key


@HOSTS
def test_refused_once_cap_is_not_consumed(cek, bind):
    ch = _channel(cek, bind)
    args = {"order_id": "o1", "subject": "alice"}
    cap = ch.mint("Order.pay", args, sub="alice", once=True)
    intent = Intent(action="Order.pay", args=args, cap=cap)
    assert _refused(ch, ch.registry.dispatch(intent))
    assert ch.registry.dispatch(intent, principal=Principal.of("alice")).ok


@pytest.mark.parametrize("cek", ["require", "off"])
def test_cap_without_subject_needs_no_principal(cek):
    ch = _channel(cek, False)
    args = {"order_id": "o1"}
    cap = ch.mint("Order.pay", args)
    assert ch.registry.dispatch(Intent(action="Order.pay", args=args, cap=cap)).ok
    r = ch.registry.dispatch(
        Intent(action="Order.pay", args=args, cap=cap), principal=Principal.of("bob")
    )
    assert r.ok, r.error
