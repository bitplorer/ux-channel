"""
AgentSession — scoped identity + budgets for agent/MCP callers.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from ux_channel.agent_runtime.policy import AgentPolicy
from ux_channel.host.context import Principal


@dataclass
class AgentSession:
    """
    One agent conversation / MCP client connection.

    Production: create per user+agent with tight policy; never share sessions
    across tenants.
    """

    agent_id: str
    policy: AgentPolicy
    session_id: str = field(default_factory=lambda: "ags_" + uuid.uuid4().hex[:16])
    principal: Optional[Principal] = None
    created_at: float = field(default_factory=time.time)
    call_count: int = 0
    window_start: float = field(default_factory=time.time)
    window_calls: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.principal is None:
            scopes = self.policy.agent_scopes
            self.principal = Principal(id=f"agent:{self.agent_id}", scopes=scopes)

    def check_budget(self) -> Optional[str]:
        """Return error code if over budget, else None."""
        if self.call_count >= self.policy.max_calls_per_session:
            return "agent_budget_session"
        now = time.time()
        if now - self.window_start >= 60:
            self.window_start = now
            self.window_calls = 0
        if self.window_calls >= self.policy.max_calls_per_minute:
            return "agent_budget_rate"
        return None

    def record_call(self) -> None:
        self.call_count += 1
        self.window_calls += 1
