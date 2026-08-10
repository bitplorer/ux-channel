"""
ChannelTest — low-ceremony tests for actions without raw Intent JSON.

::

    from ux_channel import Channel
    from ux_channel.host.testing import ChannelTest

    ch = Channel.boot(secret="…")
    t = ChannelTest(ch)
    t.call("Counter.inc", n=0).assert_ok()
    t.call("Order.refund", user_id="bob", roles=["admin"]).assert_ok()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from ux_channel.host.context import Principal
from ux_channel.protocol.types import Intent, Result


@dataclass
class CallResult:
    """Wrapper around Result with fluent assertions."""

    result: Result
    action: str
    args: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.result.ok)

    @property
    def ops(self) -> list:
        return list(self.result.ops or [])

    def assert_ok(self) -> "CallResult":
        assert self.result.ok, f"expected ok action={self.action} error={self.result.error}"
        return self

    def assert_fail(self, code: str | None = None) -> "CallResult":
        assert not self.result.ok, f"expected failure for {self.action}"
        if code is not None:
            assert self.result.error and self.result.error.code == code, self.result.error
        return self

    def assert_morph(self, uid_id: str, *, contains: str | None = None) -> "CallResult":
        targets = []
        for op in self.ops:
            if op.get("op") not in ("morph", "swap"):
                continue
            t = str(op.get("target") or "")
            html = str(op.get("html") or "")
            if uid_id in t or f'[data-channel-id="{uid_id}"]' == t or uid_id in html:
                targets.append(op)
                if contains is not None and contains not in html:
                    raise AssertionError(
                        f"morph for {uid_id!r} missing {contains!r} in html"
                    )
        assert targets, f"no morph/swap for uid {uid_id!r}; ops={[o.get('op') for o in self.ops]}"
        return self

    def assert_notice(self, message: str | None = None, *, level: str | None = None) -> "CallResult":
        return self.assert_toast(message, level=level)

    def assert_toast(self, message: str | None = None, *, level: str | None = None) -> "CallResult":
        toasts = [o for o in self.ops if o.get("op") == "toast"]
        assert toasts, f"no toast op; ops={[o.get('op') for o in self.ops]}"
        if message is not None:
            assert any(message in str(o.get("message", "")) for o in toasts), toasts
        if level is not None:
            assert any(o.get("level") == level for o in toasts), toasts
        return self

    def assert_navigate(self, href: str | None = None) -> "CallResult":
        navs = [o for o in self.ops if o.get("op") == "navigate"]
        assert navs, "no navigate op"
        if href is not None:
            assert any(href in str(o.get("href", "")) for o in navs), navs
        return self

    def html_for(self, uid_id: str) -> str:
        for op in self.ops:
            if op.get("op") in ("morph", "swap"):
                t = str(op.get("target") or "")
                if uid_id in t or f'[data-channel-id="{uid_id}"]' in t:
                    return str(op.get("html") or "")
        return ""


def _principal_from_args(
    args: Mapping[str, Any],
    *,
    principal: Any = None,
    default_sub: str | None = None,
) -> Optional[Principal]:
    """Build Principal for auth=True / roles without dropping handler args."""
    if principal is not None:
        if isinstance(principal, Principal):
            if not (principal.claims or {}).get("roles") and (
                args.get("roles") or args.get("role")
            ):
                return Principal.of(
                    principal.id,
                    roles=args.get("roles") or args.get("role"),
                    scopes=principal.scopes,
                    claims=dict(principal.claims or {}),
                )
            return principal
        return Principal.of(
            str(getattr(principal, "id", principal)),
            roles=args.get("roles") or args.get("role"),
        )
    pid = args.get("user_id") or args.get("subject") or args.get("sub") or default_sub
    if pid is None:
        return None
    return Principal.of(str(pid), roles=args.get("roles") or args.get("role"))


class ChannelTest:
    """
    Dispatch helpers bound to a Channel / ActionRegistry.

    Identity for ``auth=True``::

        .call("X", user_id="u1")
        .call("X", user_id="bob", roles=["admin"])
        .call("X", principal=Principal.of("bob", roles=["admin"]))
    """

    def __init__(self, channel_or_registry: Any, *, mint_cap: bool = True, sub: str | None = None):
        if hasattr(channel_or_registry, "registry"):
            self.channel = channel_or_registry
            self.registry = channel_or_registry.registry
        else:
            self.channel = None
            self.registry = channel_or_registry
        self.mint_cap = mint_cap
        self.sub = sub

    def call(
        self,
        action: str,
        args: Mapping[str, Any] | None = None,
        *,
        form: Mapping[str, Any] | None = None,
        cap: str | None = None,
        once: bool = False,
        principal: Any = None,
        **kwargs: Any,
    ) -> CallResult:
        # Keep user_id/roles in Intent.args for handlers + policy; also pass principal=
        call_args = dict(args or {})
        call_args.update(kwargs)
        principal = _principal_from_args(
            call_args, principal=principal, default_sub=self.sub
        )
        cap_sub = self.sub
        if principal is not None:
            cap_sub = principal.id or cap_sub

        if cap is None and self.mint_cap and getattr(self.registry, "require_cap", True):
            cap = self.registry.mint(
                action,
                call_args,
                once=once,
                sub=cap_sub,
                form=dict(form) if form else None,
            )
        intent = Intent(action=action, args=call_args, form=dict(form or {}), cap=cap)
        result = self.registry.dispatch(intent, principal=principal)
        if hasattr(result, "__await__"):
            import asyncio

            result = asyncio.get_event_loop().run_until_complete(result)
        return CallResult(result=result, action=action, args=call_args)

    def click(self, action: str, **args: Any) -> CallResult:
        return self.call(action, **args)
