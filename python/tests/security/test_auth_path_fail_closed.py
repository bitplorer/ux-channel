"""Errors on the Cap / auth path deny; they never fall back to allow."""

from __future__ import annotations

import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.devtools.ticket_revoke import (
    TicketRevocationList,
    set_revocation_list,
)
from ux_channel.enhance.attach import EnhanceFacade
from ux_channel.host.config import ChannelConfig
from ux_channel.mcp.confirm import mint_confirm_token, verify_confirm_token
from ux_channel.realtime.webrtc import sign_rtc_ticket, verify_rtc_ticket
from ux_channel.security.policy import get_policy, set_policy
from ux_channel.security.push_security import authorize_push_subscribe, sign_push_ticket
from ux_channel.workplace.ticket import (
    sign_workplace_ticket,
    verify_workplace_ticket_payload,
)

SECRET = "test-secret-key-32chars-minimum!!"


class _StoreDown(ConnectionError):
    pass


class _DownRevocationStore:
    def revoke(self, token_id: str, *, ttl_s: float = 3600) -> None:
        raise _StoreDown("revocation store unreachable")

    def is_revoked(self, token_id: str) -> bool:
        raise _StoreDown("revocation store unreachable")


@pytest.fixture
def revocation_down():
    # conftest resets the process list after each test
    set_revocation_list(TicketRevocationList(store=_DownRevocationStore()))


def _cfg(**kw):
    return ChannelConfig.development(secret=SECRET, allow_memory_stores=True, **kw)


# --- cek=require must not downgrade to native continuations ---------------


class _Reg:
    def mint(self, action, args, **kwargs):
        return f"cap:{action}"


class _Ch:
    def __init__(self, cek):
        self.registry = _Reg()
        self.config = type("C", (), {"cek": cek})()


def test_continuation_rejects_unknown_cek_mode():
    with pytest.raises(ValueError, match="ChannelConfig.cek"):
        EnhanceFacade(channel=_Ch("requre")).mint_continuation(event="click", action="A.b")


def test_continuation_surfaces_broken_cek_adapter_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "ux_channel.cek.surface_adapter", None)
    with pytest.raises(ImportError):
        EnhanceFacade(channel=_Ch("require")).mint_continuation(event="click", action="A.b")


# --- revocation store down: revoked-or-not is unknown, so deny -------------


def test_push_subscribe_fails_closed_when_revocation_store_down(revocation_down):
    cfg = _cfg(push_require_auth=True)
    ticket = sign_push_ticket(cfg, "orders")
    with pytest.raises(_StoreDown):
        authorize_push_subscribe(cfg, "orders", ticket=ticket)


def test_rtc_ticket_fails_closed_when_revocation_store_down(revocation_down):
    cfg = _cfg()
    ticket = sign_rtc_ticket(cfg, "room1")
    with pytest.raises(_StoreDown):
        verify_rtc_ticket(cfg, ticket, "room1")


def test_workplace_ticket_fails_closed_when_revocation_store_down(revocation_down):
    cfg = _cfg()
    ticket = sign_workplace_ticket(cfg, room="r1", sub="p1")
    with pytest.raises(_StoreDown):
        verify_workplace_ticket_payload(cfg, ticket, room="r1")


def test_mcp_session_revoke_reports_failure_when_revocation_store_down(revocation_down):
    app = FastAPI()
    cfg = _cfg(
        mount_agent_mcp=True,
        agent_token="dev-token",
        rate_limit_per_minute=0,
        enforce_same_origin=False,
        require_channel_header=False,
    )
    reg = ActionRegistry(secret=SECRET, require_cap=True)
    reg.config = cfg  # type: ignore[attr-defined]
    mount_channel(app, reg, config=cfg)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post(
        "/ux-channel/mcp/session/revoke",
        headers={"Authorization": "Bearer dev-token"},
        json={"ticket": "t-1"},
    )
    assert r.status_code == 500


# --- topic policy engine error: deny ----------------------------------------


class _BrokenPolicy:
    def check_topic(self, topic, principal=None):
        raise RuntimeError("policy backend down")


def test_push_subscribe_fails_closed_when_topic_policy_raises():
    prev = get_policy()
    set_policy(_BrokenPolicy())  # type: ignore[arg-type]
    try:
        cfg = _cfg(push_require_auth=True)
        ticket = sign_push_ticket(cfg, "orders")
        with pytest.raises(RuntimeError, match="policy backend down"):
            authorize_push_subscribe(cfg, "orders", ticket=ticket)
    finally:
        set_policy(prev)


# --- confirm-token replay store error: the one-time token is not accepted ---


class _BrokenNonces:
    def check_and_use(self, key):
        raise _StoreDown("nonce store unreachable")


def test_confirm_token_fails_closed_when_nonce_store_raises():
    kw = dict(action="Orders.cancel", arguments={"id": 1}, session_id="s", agent_id="a")
    tok, _ = mint_confirm_token(SECRET, **kw)
    with pytest.raises(_StoreDown):
        verify_confirm_token(SECRET, tok, nonce_store=_BrokenNonces(), **kw)
