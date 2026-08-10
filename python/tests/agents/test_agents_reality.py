"""What matters: human button path == agent dispatch; tools/situation/effects; audit."""

from __future__ import annotations

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Intent, agents, attach_audit, state
from ux_channel.devtools.agents_api import EffectReport


SECRET = "agents-reality-secret-key-32bytes!!"


def _boot(**kw):
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=SECRET, allow_memory_stores=True, require_cap=False, **kw
    )
    return Channel.boot(app, config=cfg)


def test_human_and_agent_same_handler():
    ch = _boot()
    st = state(ch)
    ag = agents(ch)
    n = st.session("n", 0)

    @ch.region("badge")
    def badge(ctx):
        return f"<b data-channel-id='badge'>{n()}</b>"

    @ch.on
    def inc():
        n.add(1)
        return ch.done(refresh=["badge"], notice="+1")

    # human-style Intent (as button would send)
    r1 = ch.registry.dispatch(Intent(action="inc", args={}, cap=ch.mint("inc", {})))
    assert r1.ok
    assert n.peek() == 1

    # agent façade
    r2 = ag.dispatch("inc", {})
    assert r2.ok
    assert n.peek() == 2

    fx = ag.effects(r2)
    assert isinstance(fx, EffectReport)
    assert fx.ok
    assert "+1" in fx.notices or fx.op_kinds


def test_tools_for_lists_registry_actions():
    ch = _boot()
    ag = agents(ch)

    @ch.on
    def greet(name: str = "world"):
        """Say hello."""
        return ch.done(notice=f"hi {name}")

    tools = ag.tools_for()
    names = [t["name"] for t in tools]
    assert "greet" in names
    g = next(t for t in tools if t["name"] == "greet")
    assert "name" in g["parameters"].get("properties", {})
    assert "hello" in g["description"].lower() or "Say" in g["description"]


def test_situation_and_block():
    ch = _boot()
    ag = agents(ch)

    @ch.on
    def a():
        pass

    @ch.on
    def b():
        pass

    ag.block("b")
    sit = ag.situation(facts={"cart": 1})
    assert sit["facts"]["cart"] == 1
    assert "a" in sit["allowed"]
    assert "b" in sit["blocked"]
    r = ag.dispatch("b", {})
    assert not r.ok


def test_audit_export_on_attach():
    ch = _boot()
    audit = attach_audit(ch)

    @ch.on
    def poke():
        return ch.done(notice="x")

    ch.registry.dispatch(Intent(action="poke", args={}, cap=ch.mint("poke", {})))
    pack = audit.export()
    assert pack["intents"]
    assert pack["frames"]
    assert pack["intents"][0]["action"] == "poke"


def test_production_config_defaults_audit():
    cfg = ChannelConfig.production(SECRET)
    assert cfg.audit is True


def test_boot_wires_agents_and_optional_audit():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False, audit=True
        ),
    )
    assert getattr(ch, "agents_api", None) is not None
    assert getattr(ch, "audit", None) is not None
