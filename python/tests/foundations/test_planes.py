"""Client/db safety (used by state())."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, state
from ux_channel.host.state_planes import ClientSafetyError


def _st(**kw):
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="x" * 40, allow_memory_stores=True, require_cap=False
        ),
    )
    return state(ch, **kw)


def test_risky_and_allowlist():
    st = _st()
    with pytest.raises(ClientSafetyError):
        st.client.set("checkout.amount", 1)
    st = _st(allow=["ui.theme"])
    r = st.client("ui.theme", "dark", persist=True)
    assert r.ops[0].get("persist") is True


def test_db_guards():
    st = _st()
    st.db.guard({"sku": "x"})
    with pytest.raises(ClientSafetyError):
        st.db.guard({"token": "abc"})
