"""Regression: soft principal + once-caps + agents façade after package import."""

from __future__ import annotations

from ux_channel import Channel, Intent, agents
from ux_channel.host.context import Principal


SECRET = "polish-auth-agents-secret-key-32b!!"


def test_soft_principal_auth_true_without_dispatch_principal():
    """Intent.args user_id alone must satisfy auth=True (no principal= kwarg)."""
    ch = Channel.boot(secret=SECRET)

    @ch.on("Secure.ping", auth=True)
    def ping(ctx):
        return ch.done(f"hi {ctx.user_id}")

    args = {"user_id": "alice"}
    cap = ch.mint("Secure.ping", args)
    r = ch.registry.dispatch(Intent(action="Secure.ping", args=args, cap=cap))
    assert r.ok, r.error
    assert any("alice" in str(o.get("message", "")) for o in r.ops)


def test_soft_principal_roles_and_once_cap_replay():
    """Roles must come from server-side principal — never Intent.args."""
    ch = Channel.boot(secret=SECRET)

    @ch.on(
        "Order.refund",
        auth=True,
        once=True,
        roles=["finance", "admin"],
        notice="Refunded",
    )
    def refund(order_id: str, ctx):
        return ch.done(f"Refunded by {ctx.user_id}")

    # Client-supplied roles are ignored (authz seal) — need principal=
    args = {"order_id": "o1", "user_id": "bob", "roles": ["finance"]}
    cap = ch.mint("Order.refund", args, once=True)
    r0 = ch.registry.dispatch(Intent(action="Order.refund", args=args, cap=cap))
    assert not r0.ok and r0.error and r0.error.code == "forbidden"

    finance = Principal.of("bob", roles=["finance"])
    cap = ch.mint("Order.refund", args, once=True, sub="bob")
    r1 = ch.registry.dispatch(
        Intent(action="Order.refund", args=args, cap=cap), principal=finance
    )
    assert r1.ok, r1.error
    r2 = ch.registry.dispatch(
        Intent(action="Order.refund", args=args, cap=cap), principal=finance
    )
    assert not r2.ok
    assert r2.error and (
        "replay" in (r2.error.message or "").lower()
        or r2.error.code in ("unauthorized", "forbidden", "bad_request")
    )

    # role gate — wrong roles on principal
    bad = {"order_id": "o2", "user_id": "carol", "roles": ["admin"]}  # args bait
    buyer = Principal.of("carol", roles=["buyer"])
    cap_b = ch.mint("Order.refund", bad, once=True, sub="carol")
    r3 = ch.registry.dispatch(
        Intent(action="Order.refund", args=bad, cap=cap_b), principal=buyer
    )
    assert not r3.ok and r3.error and r3.error.code == "forbidden"


def test_region_command_preserves_principal_on_ctx():
    """book.command must not drop ActionContext.principal when rebuilding RegionContext."""
    ch = Channel.boot(secret=SECRET)
    seen = {}

    @ch.on("Cart.add", auth=True)
    def add(sku: str, ctx):
        seen["user"] = ctx.user_id
        seen["principal"] = getattr(ctx, "principal", None)
        return ch.done("ok")

    args = {"sku": "sku1", "user_id": "dave", "tenant_id": "t9"}
    cap = ch.mint("Cart.add", args)
    r = ch.registry.dispatch(Intent(action="Cart.add", args=args, cap=cap))
    assert r.ok, r.error
    assert seen["user"] == "dave"
    assert seen["principal"] is not None
    assert getattr(seen["principal"], "id", None) == "dave"


def test_agents_facade_callable_after_agents_package_import():
    """Importing agent_runtime must not shadow root agents() function."""
    from ux_channel.agent_runtime import AgentRunner  # noqa: F401
    import ux_channel
    import types

    assert isinstance(ux_channel.agent_runtime, types.ModuleType)
    assert not callable(ux_channel.agent_runtime)
    assert callable(ux_channel.agents)
    ch = Channel.boot(secret=SECRET)
    # Prefer re-import style callers use
    from ux_channel import agents as agents_fn

    ag = agents_fn(ch)
    assert ag is not None
    assert hasattr(ag, "tools_for")
    # agent_runtime is the kernel package — not a callable façade
    from ux_channel.agent_runtime import AgentRunner
    assert AgentRunner is not None


def test_dispatch_principal_override_still_wins():
    ch = Channel.boot(secret=SECRET)

    @ch.on("Who.ami", auth=True)
    def who(ctx):
        return ch.done(str(ctx.user_id))

    # args claim alice, principal override is bob
    args = {"user_id": "alice"}
    cap = ch.mint("Who.ami", args)
    r = ch.registry.dispatch(
        Intent(action="Who.ami", args=args, cap=cap),
        principal=Principal.of("bob"),
    )
    assert r.ok, r.error
    assert any("bob" in str(o.get("message", "")) for o in r.ops)
