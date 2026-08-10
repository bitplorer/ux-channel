"""Agent / MCP policy — allow, deny, confirm, and budget guardrails for non-human callers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AbstractSet, Optional, Sequence


@dataclass(frozen=True)
class AgentPolicy:
    """
    Immutable policy for agent/MCP tool invocation.

    Defaults are fail-closed for production: empty allowlist means **deny all**
    unless ``allow_all`` is explicitly True (dev only).
    """

    # Action name allow / deny (deny wins)
    allow_actions: frozenset[str] = field(default_factory=frozenset)
    deny_actions: frozenset[str] = field(default_factory=frozenset)
    allow_all: bool = False  # NEVER True in production

    # Prefix allow (e.g. "Search.", "Docs.") — still subject to deny
    allow_prefixes: tuple[str, ...] = ()

    # Require human confirmation marker for these actions
    confirm_actions: frozenset[str] = field(default_factory=frozenset)
    confirm_prefixes: tuple[str, ...] = ()

    # Budgets (per AgentSession)
    max_calls_per_session: int = 50
    max_calls_per_minute: int = 30
    max_payload_bytes: int = 64_000

    # Tools may only run with these scopes present on Principal
    required_scopes: tuple[str, ...] = ()
    # Default principal scopes granted to the agent identity (if any)
    agent_scopes: tuple[str, ...] = ("agent:invoke",)

    # Dry-run: return planned Result without executing handler
    dry_run_default: bool = False

    # Read-only mode: only allow actions tagged read_only in tool meta
    read_only: bool = False

    def allows(self, action: str) -> bool:
        if action in self.deny_actions:
            return False
        if self.allow_all:
            return True
        if action in self.allow_actions:
            return True
        return any(action.startswith(p) for p in self.allow_prefixes)

    def needs_confirmation(self, action: str) -> bool:
        if action in self.confirm_actions:
            return True
        return any(action.startswith(p) for p in self.confirm_prefixes)

    @classmethod
    def development(cls, *allow: str, **kwargs) -> "AgentPolicy":
        """Dev convenience: allow listed actions (or all if empty and allow_all)."""
        if allow:
            return cls(allow_actions=frozenset(allow), allow_all=False, **kwargs)
        return cls(allow_all=True, max_calls_per_session=200, **kwargs)

    @classmethod
    def production(
        cls,
        allow: Sequence[str],
        *,
        confirm: Sequence[str] = (),
        deny: Sequence[str] = (),
        **kwargs,
    ) -> "AgentPolicy":
        """Fail-closed production policy — explicit allowlist required."""
        prefixes = tuple(kwargs.get("allow_prefixes") or ())
        if not allow and not prefixes:
            raise ValueError(
                "AgentPolicy.production requires a non-empty allow list "
                "or allow_prefixes (refuse open agent access)"
            )
        return cls(
            allow_actions=frozenset(allow),
            deny_actions=frozenset(deny),
            confirm_actions=frozenset(confirm),
            allow_all=False,
            **kwargs,
        )
