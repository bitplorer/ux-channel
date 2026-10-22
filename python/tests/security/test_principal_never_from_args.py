"""``ctx.principal`` is never built from client args (issue #72).

Identity comes only from ``dispatch(principal=)`` or ``auth_resolver``. Intent
args that name a caller (``principal``, ``subject``, ``user``, ``sub``,
``user_id``) never reach ``ctx.principal``, ``ctx.subject``, the identity keys
of ``ctx.meta`` / ``ctx.scope``, or ``ctx.verified``, on any dispatch path:
sync, async, batch, WebSocket, ``@ch.on`` and ``@ch.on(auth=True)``.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Intent, Result
from ux_channel.host.context import Principal
from ux_channel.transport.batch import dispatch_batch, dispatch_batch_async

SECRET = "dev-principal-never-from-args-32ch!"
SPOOF = "mallory"
SPOOF_KEYS = ("principal", "subject", "user", "sub", "user_id")
ACTIONS = ("Raw.see", "On.see")
CEK = pytest.mark.parametrize("cek", ["require", "off"])


def _boot(cek: str) -> tuple[Channel, FastAPI, list[dict]]:
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=SECRET,
        cek=cek,
        observe="off",
        ws_require_origin=False,
        push_require_auth=False,
    )
    ch = Channel.boot(app, config=cfg)
    seen: list[dict] = []

    def _record(ctx, principal, **extra):
        seen.append(
            {
                "principal": principal,
                "ctx.principal": ctx.principal,
                "ctx.subject": ctx.subject,
                "ctx.user_id": ctx.user_id,
                "verified.subject": ctx.verified.subject if ctx.verified else None,
                **extra,
            }
        )

    @ch.registry.action("Raw.see")
    def raw(ctx, principal=None, **_kw):
        _record(ctx, principal, **{f"meta.{k}": ctx.meta.get(k) for k in ("user_id", "subject", "sub")})
        return Result.success()

    @ch.on("On.see")
    def on_see(ctx, principal=None, **_kw):
        _record(
            ctx,
            principal,
            **{"ctx.actor": ctx.actor},
            **{f"scope.{k}": ctx.scope.get(k) for k in ("user_id", "subject", "sub")},
        )

    @ch.on("On.auth", auth=True)
    def on_auth(ctx, **_kw):
        seen.append({"auth.user_id": ctx.user_id})

    return ch, app, seen


def _intent(ch: Channel, action: str, args: dict) -> Intent:
    return Intent(action=action, args=args, cap=ch.mint(action, args))


def _spoof_args(key: str) -> dict:
    # "scope" reaches @ch.on handlers as their RegionContext scope.
    return {"doc": "d1", key: SPOOF, "scope": {k: SPOOF for k in SPOOF_KEYS}}


def _no_spoof(seen: list[dict]) -> None:
    assert seen, "handler did not run"
    for row in seen:
        for field, value in row.items():
            assert SPOOF not in repr(value), (field, value)


def _via_ws(app: FastAPI, intent: Intent) -> dict:
    with TestClient(app).websocket_connect("/ux-channel/ws?topics=public.x") as ws:
        ws.send_json({"type": "intent", **intent.to_dict()})
        while True:
            msg = ws.receive_json()
            if msg.get("type") == "result":
                return msg


PATHS = {
    "sync": lambda ch, app, i: ch.registry.dispatch(i).ok,
    "async": lambda ch, app, i: asyncio.run(ch.registry.async_dispatch(i)).ok,
    "batch": lambda ch, app, i: dispatch_batch(ch.registry, [i.to_dict()])["batch"][0]["ok"],
    "batch_async": lambda ch, app, i: asyncio.run(
        dispatch_batch_async(ch.registry, [i.to_dict()])
    )["batch"][0]["ok"],
    "ws": lambda ch, app, i: _via_ws(app, i)["ok"],
}


@CEK
@pytest.mark.parametrize("path", sorted(PATHS))
@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("key", SPOOF_KEYS)
def test_args_never_become_the_principal(cek, path, action, key):
    """No verified principal: identity stays None whatever the args say."""
    ch, app, seen = _boot(cek)
    assert PATHS[path](ch, app, _intent(ch, action, _spoof_args(key)))
    _no_spoof(seen)
    assert seen[0]["ctx.principal"] is None
    assert seen[0]["principal"] is None


@CEK
@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("key", SPOOF_KEYS)
def test_args_never_override_the_authenticated_principal(cek, action, key):
    ch, _app, seen = _boot(cek)
    alice = Principal.of("alice")
    assert ch.registry.dispatch(_intent(ch, action, _spoof_args(key)), principal=alice).ok
    _no_spoof(seen)
    row = seen[0]
    assert row["ctx.principal"] is alice and row["principal"] is alice
    ids = {
        v
        for k, v in row.items()
        if k not in ("principal", "ctx.principal", "verified.subject")
        and not k.startswith("meta.")  # ActionContext.meta carries no identity
    }
    assert ids == {"alice"}, row


@CEK
@pytest.mark.parametrize("key", SPOOF_KEYS)
def test_args_do_not_satisfy_auth(cek, key):
    """``@ch.on(auth=True)`` refuses a caller who only names themselves in args."""
    ch, _app, seen = _boot(cek)
    r = ch.registry.dispatch(_intent(ch, "On.auth", _spoof_args(key)))
    assert not r.ok and r.error.code == "unauthorized", r.error
    assert seen == []
    r = ch.registry.dispatch(
        _intent(ch, "On.auth", _spoof_args(key)), principal=Principal.of("alice")
    )
    assert r.ok, r.error
    assert seen == [{"auth.user_id": "alice"}]


@CEK
@pytest.mark.parametrize("key", SPOOF_KEYS)
def test_args_do_not_satisfy_require_principal(cek, key):
    ch, _app, seen = _boot(cek)
    ch.registry.require_principal = True
    r = ch.registry.dispatch(_intent(ch, "Raw.see", _spoof_args(key)))
    assert not r.ok and r.error.code == "unauthorized", r.error
    assert seen == []
