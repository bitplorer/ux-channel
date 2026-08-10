"""Integration: Channel boot → mint → dispatch → Result (application path)."""
from __future__ import annotations

from ux_channel import Channel, ChannelConfig, Intent, Result
from ux_channel.protocol.capability import CapService


SECRET = "integration-test-secret-32chars!!!"


def _boot(**kw):
    return Channel.boot(
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            rate_limit_per_minute=0,
            **kw,
        ),
    )


def test_action_dispatch_with_cap():
    ch = _boot()

    @ch.on("It.echo")
    def echo(ctx, n: int = 0):
        from ux_channel.protocol.ops import toast

        return Result(ok=True, ops=[toast(f"n={n}")])

    args = {"n": 3}
    cap = ch.registry.mint("It.echo", args)
    r = ch.registry.dispatch(Intent(action="It.echo", args=args, cap=cap))
    assert r.ok, getattr(r, "error", r)
    assert any(o.get("op") == "toast" for o in r.ops)


def test_bad_cap_fails_closed():
    ch = _boot()

    @ch.on("It.secure")
    def secure(ctx):
        return Result(ok=True, ops=[])

    r2 = ch.registry.dispatch(Intent(action="It.secure", args={}, cap="garbage"))
    assert not r2.ok


def test_registry_mint_dispatch_roundtrip():
    ch = _boot()
    args = {"sku": "a", "qty": 1}

    @ch.on("Cart.demo")
    def demo(ctx, sku: str = "", qty: int = 0):
        return Result(ok=True, ops=[])

    tok = ch.registry.mint("Cart.demo", args)
    r = ch.registry.dispatch(Intent(action="Cart.demo", args=args, cap=tok))
    assert r.ok, getattr(r, "error", r)


def test_python_hash_args_matches_rust_oracle():
    assert CapService.hash_args({"sku": "abc-123", "qty": 2}) == (
        "96e4f83e3793b646323a67f314b51044"
    )
