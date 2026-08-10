"""Error-handling patterns for ux-channel (importable + tested).

Every failure is still a **Result**: ``ok=False`` + stable ``error.code``.
HTTP status is secondary (see ``error_map``). Clients branch on ``ok`` / code.
"""

from __future__ import annotations

from typing import Any

from ux_channel import Channel, ChannelConfig
from ux_channel.error_map import ensure_error_meta, http_status_for
from ux_channel.errors import ActionError
from ux_channel.ops import morph, toast
from ux_channel.registry import ActionRegistry
from ux_channel.types import Intent, Result


# ── 1. Result.failure (no Channel) ───────────────────────────────────────


def pattern_result_failure() -> Result:
    """Pure Result: validation + field map + optional UI ops."""
    form_html = '<form id="login"><input name="email" class="err"/></form>'
    return Result.failure(
        "validation",
        "Please fix the highlighted fields",
        morph("#login", form_html),
        toast("Invalid email", level="error"),
        fields={"email": ["required", "must be an email"]},
        retryable=False,
    )


def pattern_retryable_rate() -> Result:
    """Rate limit — clients may retry (error_map marks retryable)."""
    return Result.failure(
        "rate_limited",
        "Too many requests",
        retryable=True,
        retry_after=30,  # lands in Result.meta
    )


# ── 2. raise ActionError (handler style) ─────────────────────────────────


def pattern_raise_action_error(reg: ActionRegistry) -> Result:
    """Registry converts ActionError → ok=false Result."""

    @reg.action("signup")
    def signup(ctx, email: str = ""):
        if not email or "@" not in email:
            raise ActionError(
                "validation",
                "Invalid email",
                fields={"email": ["required"]},
            )
        return Result.success(toast(f"welcome {email}"))

    return reg.dispatch(Intent(action="signup", args={"email": ""}, request_id="e1"))


# ── 3. Product speech: ch.fail.* ─────────────────────────────────────────


def _boot_channel() -> Channel:
    from fastapi import FastAPI

    return Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="error-examples-secret-key-32chars!!!",
            allow_memory_stores=True,
            require_cap=False,
        ),
    )


def pattern_ch_fail_valid(ch: Channel) -> Result:
    """Form re-morph with field errors (HTTP 422)."""
    return ch.fail.valid(
        {"email": ["required"], "password": ["min 8 chars"]},
        region="Form:root",
        html='<form id="Form:root"><!-- re-rendered with errors --></form>',
        message="Fix the form",
        focus="#email",
        notice=True,
    )


def pattern_ch_fail_auth(ch: Channel) -> Result:
    return ch.fail.auth("Sign in to continue")


def pattern_ch_fail_forbidden(ch: Channel) -> Result:
    return ch.fail.forbidden("Admins only")


def pattern_ch_fail_rate(ch: Channel) -> Result:
    return ch.fail.rate("Slow down")


def pattern_ch_fail_code(ch: Channel) -> Result:
    """Any stable code: not_found, conflict, internal, …"""
    return ch.fail.code("conflict", "Order already paid")


def pattern_handler_with_fail(ch: Channel) -> Result:
    """Real action: branch and return ch.fail / ch.done."""

    @ch.on("transfer")
    def transfer(ctx, amount: float = 0, balance: float = 0):
        if amount <= 0:
            return ch.fail.valid(
                {"amount": ["must be positive"]},
                region="Transfer:form",
                html="<div id='Transfer:form'>bad amount</div>",
                message="Check amount",
            )
        if amount > balance:
            return ch.fail.code("forbidden", "Insufficient funds")
        return ch.done(toast(f"sent {amount}"))

    return ch.registry.dispatch(
        Intent(
            action="transfer",
            args={"amount": 50, "balance": 10},
            request_id="t1",
        )
    )


# ── 4. Mapping: HTTP + client kind ───────────────────────────────────────


def pattern_map_status(result: Result) -> dict[str, Any]:
    """What hosts use for status lines / client error plane."""
    ensure_error_meta(result)
    code = result.error.code if result.error else None
    return {
        "ok": result.ok,
        "code": code,
        "http_status": http_status_for(result),
        "error_kind": (result.meta or {}).get("error_kind"),
        "retryable": result.error.retryable if result.error else None,
        "meta_retryable": (result.meta or {}).get("error.retryable")
        or (result.meta or {}).get("retryable"),
    }


# ── 5. DX / CLI errors ───────────────────────────────────────────────────


def pattern_dx_usage() -> dict[str, Any]:
    from ux_channel.dx_errors import DxUsageError

    err = DxUsageError("missing --out", hint="uxchannel dashboard --out reports/dx")
    return err.as_dict()


def run_all() -> list[dict[str, Any]]:
    """Execute every pattern; return a small report for CLI/tests."""
    report: list[dict[str, Any]] = []

    r = pattern_result_failure()
    report.append({"name": "result_failure", "map": pattern_map_status(r), "ops": len(r.ops)})

    r = pattern_retryable_rate()
    report.append({"name": "retryable_rate", "map": pattern_map_status(r)})

    reg = ActionRegistry(
        secret="error-examples-secret-key-32chars!!!",
        require_cap=False,
    )
    r = pattern_raise_action_error(reg)
    report.append({"name": "raise_action_error", "map": pattern_map_status(r), "fields": r.error.fields if r.error else None})

    ch = _boot_channel()
    for name, fn in [
        ("ch_fail_valid", pattern_ch_fail_valid),
        ("ch_fail_auth", pattern_ch_fail_auth),
        ("ch_fail_forbidden", pattern_ch_fail_forbidden),
        ("ch_fail_rate", pattern_ch_fail_rate),
        ("ch_fail_code", pattern_ch_fail_code),
        ("handler_with_fail", pattern_handler_with_fail),
    ]:
        r = fn(ch)
        report.append({"name": name, "map": pattern_map_status(r)})

    report.append({"name": "dx_usage", "dx": pattern_dx_usage()})
    return report
