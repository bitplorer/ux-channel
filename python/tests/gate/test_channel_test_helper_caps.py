"""ChannelTest mints the Cap the registry will verify, for every setting."""
from __future__ import annotations

import pytest

from ux_channel import ActionRegistry, ChannelConfig, Result
from ux_channel.host.testing import ChannelTest
from ux_channel import Principal

SECRET = "dev-secret-key-32chars-minimum!!!!"


def _registry(**kw) -> ActionRegistry:
    reg = ActionRegistry(secret=SECRET, require_cap=True, **kw)

    @reg.action("Login.save")
    def save(email: str = ""):
        return Result.success() if "@" in email else Result.failure("validation", "bad")

    return reg


@pytest.mark.parametrize("verify_form_in_cap", [False, True])
def test_call_with_form_verifies(verify_form_in_cap):
    reg = _registry(verify_form_in_cap=verify_form_in_cap)
    res = ChannelTest(reg).call("Login.save", form={"email": "a@b.c"})
    assert res.result.ok, res.result.error


@pytest.mark.parametrize("verify_form_in_cap", [False, True])
def test_call_without_form_verifies(verify_form_in_cap):
    reg = _registry(verify_form_in_cap=verify_form_in_cap)
    res = ChannelTest(reg).call("Login.save", email="a@b.c")
    assert res.result.ok, res.result.error


def test_form_is_sealed_only_when_registry_verifies_it(monkeypatch):
    for flag, expect_sealed in ((False, False), (True, True)):
        reg = _registry(verify_form_in_cap=flag)
        seen: dict = {}
        real = reg.mint

        def spy(action, args=None, **kw):
            seen["args"], seen["kw"] = dict(args or {}), kw
            return real(action, args, **kw)

        monkeypatch.setattr(reg, "mint", spy)
        ChannelTest(reg).call("Login.save", form={"email": "a@b.c"})
        assert ("email" in seen["args"]) is expect_sealed, flag
        assert "form" not in seen["kw"], "form is never a Cap extra"


@pytest.mark.parametrize("bind", [False, True])
def test_cap_subject_comes_from_registry(bind, monkeypatch):
    reg = _registry(config=ChannelConfig(secret=SECRET, bind_cap_to_principal=bind))
    calls: list = []
    real = reg._cap_expected_sub

    def spy(principal):
        calls.append(principal)
        return real(principal)

    monkeypatch.setattr(reg, "_cap_expected_sub", spy)
    res = ChannelTest(reg).call(
        "Login.save", email="a@b.c", principal=Principal.of("bob")
    )
    assert res.result.ok, res.result.error
    assert calls, "ChannelTest must ask the registry for the expected subject"
