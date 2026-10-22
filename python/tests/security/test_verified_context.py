"""ctx.verified carries only what the Cap Host verified, never Intent args."""

from __future__ import annotations

import asyncio

import pytest

from ux_channel import Channel, ChannelConfig, Intent, Result, VerifiedContext
from ux_channel.host.context import Principal

SECRET = "dev-verified-context-32chars-min!!!"

HOSTS = pytest.mark.parametrize("cek", ["require", "off"], ids=["cek", "classic"])

FORGED = {
    "principal": "mallory",
    "subject": "mallory",
    "sub": "mallory",
    "user_id": "mallory",
    "verified": {"subject": "mallory"},
    "ctx": {"verified": {"subject": "mallory"}},
}


def _channel(cek: str) -> tuple[Channel, list]:
    ch = Channel.boot(config=ChannelConfig.development(secret=SECRET, cek=cek))
    seen: list = []

    @ch.registry.action("Doc.edit")
    def edit(ctx, **_args):
        seen.append(ctx.verified)
        return Result.success()

    @ch.registry.action("Doc.view")
    async def view(ctx, **_args):
        seen.append(ctx.verified)
        return Result.success()

    @ch.on("Doc.share")  # product door: handler gets a RegionContext
    def share(ctx, **_args):
        seen.append(ctx.verified)

    return ch, seen


@HOSTS
def test_verified_context_is_built_from_the_cap(cek):
    ch, seen = _channel(cek)
    args = {"doc": "d1"}
    cap = ch.mint("Doc.edit", args, sub="alice")
    r = ch.registry.dispatch(
        Intent(action="Doc.edit", args=args, cap=cap), principal=Principal.of("alice")
    )
    assert r.ok, r.error
    (v,) = seen
    assert isinstance(v, VerifiedContext)
    assert (v.action, v.subject) == ("Doc.edit", "alice")
    assert v.claims["action"] == "Doc.edit"
    with pytest.raises(TypeError):
        v.claims["subject"] = "mallory"  # type: ignore[index]
    with pytest.raises(AttributeError):
        v.subject = "mallory"  # type: ignore[misc]


@HOSTS
def test_client_principal_or_subject_in_args_never_reaches_verified(cek):
    """Forged identity keys in args (sealed or not) leave ctx.verified untouched."""
    ch, seen = _channel(cek)
    args = {"doc": "d1", **FORGED}
    cap = ch.mint("Doc.edit", args)  # no subject: args are sealed, not a subject
    assert ch.registry.dispatch(Intent(action="Doc.edit", args=args, cap=cap)).ok
    cap = ch.mint("Doc.edit", args, sub="alice")
    assert ch.registry.dispatch(
        Intent(action="Doc.edit", args=args, cap=cap), principal=Principal.of("alice")
    ).ok
    cap = ch.mint("Doc.view", args, sub="alice")
    assert asyncio.run(
        ch.registry.async_dispatch(
            Intent(action="Doc.view", args=args, cap=cap),
            principal=Principal.of("alice"),
        )
    ).ok
    cap = ch.mint("Doc.share", args, sub="alice")
    assert ch.registry.dispatch(
        Intent(action="Doc.share", args=args, cap=cap), principal=Principal.of("alice")
    ).ok
    assert [v.subject for v in seen] == [None, "alice", "alice", "alice"]
    for v in seen:
        assert "mallory" not in repr(v), v


def test_no_cap_means_no_verified_context():
    ch = Channel.boot(
        config=ChannelConfig.development(secret=SECRET, cek="off", require_cap=False)
    )
    seen: list = []

    @ch.registry.action("Doc.open")
    def open_doc(ctx, **_args):
        seen.append(ctx.verified)
        return Result.success()

    assert ch.registry.dispatch(Intent(action="Doc.open", args=FORGED)).ok
    assert seen == [None]


def _mutations(claims) -> list:
    """Every way a handler could try to change nested claims."""
    scopes, extra = claims["scopes"], claims.get("extra")
    attempts = [
        lambda: scopes.append("admin"),
        lambda: scopes.__setitem__(0, "admin"),
        lambda: scopes.extend(["admin"]),
    ]
    if extra is not None:
        attempts += [
            lambda: extra.__setitem__("tier", "gold"),
            lambda: extra.__delitem__("tier"),
            lambda: extra.update(tier="gold"),
            lambda: extra["tier"]["levels"].append(9),
            lambda: extra["tier"].__setitem__("levels", ()),
            lambda: extra["tags"].add("admin"),
        ]
    return attempts


@HOSTS
def test_nested_claims_cannot_be_mutated(cek):
    ch, seen = _channel(cek)
    args = {"doc": "d1"}
    mint_kw: dict = {"sub": "alice", "scopes": ["Doc.edit"]}
    if cek == "off":  # classic keeps extra kwargs as a claim; cek seals them into args
        mint_kw.update(tier={"levels": [1, 2]}, tags=["a"])
    cap = ch.mint("Doc.edit", args, **mint_kw)
    assert ch.registry.dispatch(
        Intent(action="Doc.edit", args=args, cap=cap), principal=Principal.of("alice")
    ).ok
    (v,) = seen
    for attempt in _mutations(v.claims):
        with pytest.raises((TypeError, AttributeError)):
            attempt()
    assert v.claims["scopes"] == ("Doc.edit",)


def test_from_claims_freezes_every_level():
    claims = {
        "action": "Doc.edit",
        "sub": "alice",
        "scopes": ["orders:write"],
        "extra": {"tier": {"levels": [1, 2]}, "tags": ["a"], "set": {"x"}},
    }
    v = VerifiedContext.from_claims(claims)
    for attempt in _mutations(v.claims) + [lambda: v.claims["extra"]["set"].add("y")]:
        with pytest.raises((TypeError, AttributeError)):
            attempt()
    claims["scopes"].append("admin")
    claims["extra"]["tier"]["levels"].append(3)
    assert v.claims["scopes"] == ("orders:write",)
    assert v.claims["extra"]["tier"]["levels"] == (1, 2)
