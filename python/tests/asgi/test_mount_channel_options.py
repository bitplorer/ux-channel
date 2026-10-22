"""mount_channel reads every option it accepts and refuses the rest."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry
from ux_channel.asgi.fastapi import FastAPIHostAdapter, mount_channel
from ux_channel.host.config import ChannelConfig

SECRET = "test-secret-key-32chars-minimum!!"


def _reg() -> ActionRegistry:
    return ActionRegistry(secret=SECRET, require_cap=True)


def _cfg(**kw) -> ChannelConfig:
    return ChannelConfig.development(
        secret=SECRET, enforce_same_origin=False, rate_limit_per_minute=0, **kw
    )


def _mcp_status(app: FastAPI) -> int:
    return TestClient(app).get("/ux-channel/mcp/tools").status_code


@pytest.mark.parametrize("config", [None, _cfg()], ids=["no-config", "config-off"])
def test_mount_agent_mcp_argument_mounts_mcp_routes(config):
    app = FastAPI()
    mount_channel(app, _reg(), config=config, mount_agent_mcp=True)
    assert _mcp_status(app) == 401  # mounted, and still needs the agent token


def test_mcp_routes_absent_by_default():
    app = FastAPI()
    mount_channel(app, _reg(), config=_cfg())
    assert _mcp_status(app) == 404


@pytest.mark.parametrize("option", ["include_bridge_js", "bogus_kw"])
def test_unknown_option_raises(option):
    with pytest.raises(TypeError, match=option):
        mount_channel(FastAPI(), _reg(), config=_cfg(), **{option: True})


def test_host_adapter_forwards_unknown_option_as_error():
    with pytest.raises(TypeError, match="bogus_kw"):
        FastAPIHostAdapter().mount(FastAPI(), _reg(), config=_cfg(), bogus_kw=1)
