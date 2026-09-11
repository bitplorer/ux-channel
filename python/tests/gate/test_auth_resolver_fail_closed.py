"""auth_resolver exceptions fail closed — not anonymous dispatch."""

from __future__ import annotations

from ux_channel.host.config import ChannelConfig
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Intent, Result
from ux_channel.security.security_events import get_security_bus


SECRET = "gate-auth-resolver-fail-32chars!!"


def test_auth_resolver_exception_is_unauthorized():
    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=False,
        cek="off",
    )
    reg = ActionRegistry.from_config(cfg)

    def boom(_request):
        raise RuntimeError("idp down")

    reg.auth_resolver = boom

    @reg.action("ping")
    def ping():
        return Result.success()

    bus = get_security_bus()
    r = reg.dispatch(Intent(action="ping", args={}))
    assert r.ok is False
    assert r.error is not None
    assert r.error.code == "unauthorized"
    assert "auth_resolver failed" in (r.error.message or "")
    kinds = [e["kind"] for e in bus.recent()]
    assert "auth_resolver_failed" in kinds
