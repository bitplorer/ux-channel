"""``ctx.scope`` holds only trusted keys; client args live in ``ctx.args``.

In an action, ``RegionContext.scope`` is built from the authenticated
principal alone: its id, roles and ``*_id`` claims. Client args such as
``tenant_id``, ``roles``, ``role``, ``actor`` or a ``scope`` dict never enter
it and never override it. They are readable, as untrusted client data, in
``RegionContext.args``. ``ActionContext.meta`` and ``ctx.key()`` never see
args either. Checked on sync, async, batch, batch-async and WebSocket
dispatch, for ``@ch.on`` handlers, the regions they refresh, and
``registry.action`` handlers.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Intent, Result
from ux_channel.host.context import Principal
from ux_channel.transport.batch import dispatch_batch, dispatch_batch_async

SECRET = "dev-scope-trusted-only-32chars-min!"
BOB = Principal.of("bob", roles=["viewer"], claims={"tenant_id": "t-bob"})
EVIL = {"tenant_id": "t-evil", "roles": ["admin"], "role": "admin", "actor": "mallory"}
ARGS = {"doc": "d1", **EVIL, "scope": dict(EVIL)}
KEYS = (*EVIL, "user_id", "subject", "sub")
BOB_SCOPE = {
    "tenant_id": "t-bob",
    "roles": ["viewer"],
    "role": None,
    "actor": None,
    "user_id": "bob",
    "subject": "bob",
    "sub": "bob",
}


def _boot(cek: str) -> tuple[Channel, FastAPI, dict]:
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=SECRET,
        cek=cek,
        observe="off",
        ws_require_origin=False,
        push_require_auth=False,
    )
    ch = Channel.boot(app, config=cfg)
    seen: dict = {}

    @ch.region("Doc.panel")
    def panel(ctx):
        seen["region.scope"] = {k: ctx.scope.get(k) for k in KEYS}
        return {}

    @panel.paint
    def _paint(_data, _ctx):
        return "<p></p>"

    @ch.on("Doc.on", refresh=[panel])
    def on(ctx, **_kw):
        seen["on.scope"] = {k: ctx.scope.get(k) for k in KEYS}
        seen["on.key"] = {k: ctx.key(k) for k in KEYS}
        seen["on.args"] = dict(getattr(ctx, "args", {}))  # main has no ctx.args

    @ch.registry.action("Doc.raw")
    def raw(ctx, **_kw):
        seen["raw.meta"] = dict(ctx.meta)
        seen["raw.key"] = {k: ctx.key(k) for k in ("tenant_id", "roles", "actor")}
        return Result.success()

    return ch, app, seen


def _via_ws(app: FastAPI, intent: Intent) -> bool:
    with TestClient(app).websocket_connect("/ux-channel/ws?topics=public.x") as ws:
        ws.send_json({"type": "intent", **intent.to_dict()})
        while True:
            msg = ws.receive_json()
            if msg.get("type") == "result":
                return msg["ok"]


PATHS = {
    "sync": lambda ch, app, i: ch.registry.dispatch(i).ok,
    "async": lambda ch, app, i: asyncio.run(ch.registry.async_dispatch(i)).ok,
    "batch": lambda ch, app, i: dispatch_batch(ch.registry, [i.to_dict()])["batch"][0]["ok"],
    "batch_async": lambda ch, app, i: asyncio.run(
        dispatch_batch_async(ch.registry, [i.to_dict()])
    )["batch"][0]["ok"],
    "ws": lambda ch, app, i: _via_ws(app, i),
}
CEK = pytest.mark.parametrize("cek", ["require", "off"])
PATH = pytest.mark.parametrize("path", sorted(PATHS))


def _run(cek: str, path: str, action: str, *, principal: Principal | None) -> dict:
    ch, app, seen = _boot(cek)
    ch.registry.auth_resolver = lambda _request: principal
    assert PATHS[path](ch, app, Intent(action=action, args=ARGS, cap=ch.mint(action, ARGS)))
    return seen


@CEK
@PATH
def test_args_never_override_principal_scope(cek, path):
    seen = _run(cek, path, "Doc.on", principal=BOB)
    assert seen["on.scope"] == BOB_SCOPE
    assert seen["region.scope"] == BOB_SCOPE
    assert seen["on.key"] == BOB_SCOPE


@CEK
@PATH
def test_args_never_enter_scope_without_principal(cek, path):
    seen = _run(cek, path, "Doc.on", principal=None)
    nothing = dict.fromkeys(KEYS)
    assert seen["on.scope"] == nothing
    assert seen["region.scope"] == nothing
    assert seen["on.key"] == nothing


@CEK
@PATH
@pytest.mark.parametrize("principal", [BOB, None], ids=["bob", "anon"])
def test_client_args_are_in_ctx_args_only(cek, path, principal):
    seen = _run(cek, path, "Doc.on", principal=principal)
    assert seen["on.args"] == ARGS


@CEK
@PATH
@pytest.mark.parametrize("principal", [BOB, None], ids=["bob", "anon"])
def test_action_context_never_sees_args(cek, path, principal):
    seen = _run(cek, path, "Doc.raw", principal=principal)
    assert seen["raw.meta"] == {}
    claims = {"tenant_id": "t-bob", "roles": ["viewer"]} if principal else {}
    assert seen["raw.key"] == {"tenant_id": None, "roles": None, "actor": None, **claims}


def test_ctx_args_is_read_only():
    ch, _app, _seen = _boot("off")

    @ch.on("Doc.write")
    def write(ctx, **_kw):
        with pytest.raises(TypeError):
            ctx.args["tenant_id"] = "t-evil"  # type: ignore[index]

    args = {"tenant_id": "t1"}
    assert ch.registry.dispatch(Intent(action="Doc.write", args=args, cap=ch.mint("Doc.write", args))).ok
