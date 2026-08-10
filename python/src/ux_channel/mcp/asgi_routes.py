"""
HTTP routes for agent/MCP tool access (modular mount).

Mounted at ``{path}/mcp`` when ``mount_agent_mcp=True``.

Security:
  * Bootstrap: ``Authorization: Bearer <agent_token>``
  * Session:   ``Authorization: Bearer <mcp_session_ticket>``
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from ux_channel.agent_runtime.tool_audit import LoggingAuditSink, MemoryAuditSink, MultiAuditSink
from ux_channel.agent_runtime.policy import AgentPolicy
from ux_channel.agent_runtime.runner import AgentRunner
from ux_channel.agent_runtime.session import AgentSession
from ux_channel.mcp.adapter import McpToolAdapter
from ux_channel.mcp.sessions import McpSession, get_session_store
from ux_channel.mcp.verticals import register_builtin_verticals
from ux_channel.host.registry import ActionRegistry


def build_agent_session(
    *,
    agent_id: str,
    policy: AgentPolicy,
    session_id: Optional[str] = None,
) -> AgentSession:
    """Construct an AgentSession (optional fixed session_id for claim-bound MCP)."""
    s = AgentSession(agent_id=agent_id, policy=policy)
    if session_id:
        s.session_id = session_id
    return s


def create_mcp_adapter(
    registry: ActionRegistry,
    *,
    policy: AgentPolicy,
    agent_id: str = "http-mcp",
    audit: Any = None,
    confirmation_secret: Optional[str] = None,
    only_marked: bool = True,
    verticals: Sequence[str] = (),
    resource_regions: Sequence[str] = (),
    room: str = "",
    scopes: Sequence[str] = (),
    sub: str = "",
    channel: Any = None,
    session_id: Optional[str] = None,
) -> McpToolAdapter:
    """
    Wire AgentRunner + McpToolAdapter for one HTTP request / session.

    When ``scopes`` is set, attaches a Principal so policy.required_scopes can apply.
    Confirmation secret falls back to channel/registry secret for signed tokens.
    """
    session = AgentSession(agent_id=agent_id, policy=policy)
    if session_id:
        session.session_id = session_id
    # attach principal scopes when claim-bound
    if scopes:
        try:
            from ux_channel.host.context import Principal

            session.principal = Principal(
                id=sub or agent_id, scopes=tuple(scopes)
            )
        except Exception:
            pass
    secret = confirmation_secret
    if not secret and getattr(registry, "config", None) is not None:
        secret = getattr(registry.config, "agent_confirmation_secret", None) or getattr(
            registry.config, "secret", None
        )
    runner = AgentRunner(
        registry,
        session,
        audit=audit or MultiAuditSink(LoggingAuditSink(), MemoryAuditSink()),
        confirmation_secret=secret,
    )
    return McpToolAdapter(
        runner,
        only_marked=only_marked,
        verticals=verticals,
        resource_regions=resource_regions,
        room=room,
        scopes=scopes,
        sub=sub,
        channel=channel,
    )


def resolve_mcp_auth(
    request: Any,
    *,
    agent_token: Optional[str],
) -> tuple[bool, Optional[McpSession], str]:
    """
    Returns (ok, session_or_none, mode).

    mode: "token" | "session" | "none"
    """
    auth = (request.headers.get("authorization") or "").strip()
    bearer = ""
    if auth.lower().startswith("bearer "):
        bearer = auth.split(" ", 1)[1].strip()
    header_tok = request.headers.get("x-channel-agent-token") or ""
    ticket_hdr = request.headers.get("x-channel-mcp-ticket") or ""

    # session ticket first
    cand = ticket_hdr or bearer
    if cand:
        sess = get_session_store().get_by_ticket(cand)
        if sess is not None:
            return True, sess, "session"

    # bootstrap agent token
    if agent_token:
        if bearer == agent_token or header_tok == agent_token:
            return True, None, "token"
    return False, None, "none"
