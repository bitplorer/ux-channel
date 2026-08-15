"""Production go/no-go — same checklist as SECURITY_AUDIT.md deploy list.

Channel.doctor() historically always returned ok=True. This module is the
contract: CLI ``uxchannel doctor --fail`` and tests assert these rows.

Does not grow root ``__all__``.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = ["production_go_nogo", "merge_go_nogo", "CHECKLIST"]

# Mirrors python/docs/security/SECURITY_AUDIT.md → Production deploy checklist.
CHECKLIST = (
    "secret_length",
    "require_cap",
    "require_channel_header",
    "memory_stores",
    "redis_or_opt_in",
    "morph_html_policy",
    "agent_token",
    "push_open",
    "trace_payloads",
    "trusted_proxy",
    "cek_extra",
)


def production_go_nogo(config: Any) -> dict[str, Any]:
    """Return ``{ok, go, no_go, checks, hints}`` for a ChannelConfig."""
    checks: list[dict[str, Any]] = []
    hints: list[str] = []

    def row(name: str, ok: bool, detail: str, *, fatal: bool = True) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail, "fatal": fatal})
        if not ok:
            hints.append(detail)

    if config is None:
        return {
            "ok": False,
            "go": False,
            "no_go": ["no ChannelConfig"],
            "checks": [{"name": "config", "ok": False, "detail": "missing config", "fatal": True}],
            "hints": ["Boot with ChannelConfig.production(secret=…) or .development()"],
            "environment": None,
        }

    env = str(getattr(config, "environment", "") or "")
    secret = str(getattr(config, "secret", "") or "")
    require_cap = bool(getattr(config, "require_cap", True))
    require_header = bool(getattr(config, "require_channel_header", True))
    allow_mem = bool(getattr(config, "allow_memory_stores", False))
    redis_url = getattr(config, "redis_url", None)
    morph = str(getattr(config, "morph_html_policy", "off") or "off")
    mount_mcp = bool(getattr(config, "mount_agent_mcp", False))
    agent_token = getattr(config, "agent_token", None)
    push_open = bool(getattr(config, "push_open", False))
    trace_on = bool(getattr(config, "trace_enabled", False))
    trace_payloads = bool(getattr(config, "trace_capture_payloads", False))
    trusted_proxy = bool(getattr(config, "trusted_proxy", False))
    cek = str(getattr(config, "cek", "off") or "off")

    if env == "production":
        row(
            "secret_length",
            len(secret) >= 32,
            "production secret must be ≥ 32 bytes (UX_CHANNEL_SECRET)",
        )
        row(
            "require_cap",
            require_cap,
            "require_cap=False is not shippable — keep True; use ch.control",
        )
        row(
            "require_channel_header",
            require_header,
            "require_channel_header=False weakens CSRF (X-UID-Channel)",
        )
        durable = bool(redis_url)
        row(
            "memory_stores",
            (not allow_mem) or durable,
            "production + allow_memory_stores without Redis is a no-go "
            "(once/rate/state are process-local). Set REDIS_URL or drop the opt-in.",
        )
        row(
            "redis_or_opt_in",
            durable or allow_mem,
            "production needs REDIS_URL or an explicit allow_memory_stores=True "
            "(single-worker only)",
        )
        row(
            "morph_html_policy",
            True,
            "morph_html_policy=off: app must escape user strings "
            "(HIGH residual). Set morph_html_policy='strict' to strip script/on*.",
            fatal=False,
        )
        if morph == "off":
            hints.append(
                "morph_html_policy=off — escape user HTML or set morph_html_policy='strict'"
            )
        if mount_mcp:
            row(
                "agent_token",
                bool(agent_token),
                "mount_agent_mcp=True requires agent_token (fail closed)",
            )
        else:
            row("agent_token", True, "agent/MCP not mounted", fatal=False)
        row(
            "push_open",
            not push_open,
            "push_open=True is not allowed in production",
        )
        row(
            "trace_payloads",
            not (trace_on and trace_payloads),
            "trace_capture_payloads=True in production may record PII",
            fatal=False,
        )
        row(
            "trusted_proxy",
            not trusted_proxy,
            "trusted_proxy=True without edge XFF rewrite is spoofable",
            fatal=False,
        )
        if cek in ("adapt", "require"):
            from ux_channel.cek.config import cek_available

            row(
                "cek_extra",
                cek_available(),
                f"cek={cek} needs pip install 'ux-channel[cek]'",
            )
        else:
            row("cek_extra", True, "cek=off (today's path)", fatal=False)
    else:
        row("secret_length", len(secret) >= 8, "dev secret too short", fatal=False)
        row("require_cap", True, "development — require_cap not gated", fatal=False)
        row("require_channel_header", True, "development CSRF relaxed", fatal=False)
        row("memory_stores", True, "development allows memory stores", fatal=False)
        row("redis_or_opt_in", True, "development", fatal=False)
        row("morph_html_policy", True, f"morph_html_policy={morph}", fatal=False)
        row("agent_token", True, "development", fatal=False)
        row("push_open", True, "development", fatal=False)
        row("trace_payloads", True, "development", fatal=False)
        row("trusted_proxy", True, "development", fatal=False)
        row("cek_extra", True, f"cek={cek}", fatal=False)
        hints.append("development defaults: fine for local; use production() for deploy")

    fatal_fail = [c for c in checks if (not c["ok"]) and c.get("fatal", True)]
    ok = not fatal_fail
    return {
        "ok": ok,
        "go": ok,
        "no_go": [c["detail"] for c in fatal_fail],
        "checks": checks,
        "hints": hints,
        "environment": env,
        "checklist": list(CHECKLIST),
    }


def merge_go_nogo(report: Mapping[str, Any] | None, config: Any) -> dict[str, Any]:
    """Fold go/no-go into an existing Channel.doctor() dict."""
    body = dict(report or {})
    gn = production_go_nogo(config)
    body["go"] = gn["go"]
    body["no_go"] = gn["no_go"]
    body["checks"] = gn["checks"]
    # Instance doctor used to hardcode ok=True. Production no-go flips it.
    if gn["environment"] == "production":
        body["ok"] = bool(gn["ok"])
    else:
        body["ok"] = bool(body.get("ok", True))
    hints = list(body.get("hints") or [])
    for h in gn["hints"]:
        if h not in hints:
            hints.append(h)
    body["hints"] = hints
    next_steps = list(body.get("next") or [])
    for cmd in (
        "uxchannel doctor --fail",
        "uxchannel upgrade-check . --fail",
        "export UX_CHANNEL_STRICT_DX=1",
    ):
        if cmd not in next_steps:
            next_steps.append(cmd)
    body["next"] = next_steps
    return body
