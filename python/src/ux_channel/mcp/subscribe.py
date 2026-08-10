"""
MCP resource subscribe — invalidate/notify over the channel push bus (SSE).

Topic scheme (public-safe prefixes for push_allow_public or ticketed):
  mcp.resource.{room}
  mcp.resource.session.{session_id}
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ux_channel.transport.push import get_push_bus

__all__ = [
    "resource_topic_for_room",
    "resource_topic_for_session",
    "subscribe_info",
    "publish_resource_event",
    "publish_effects_invalidation",
]


def resource_topic_for_room(room: str) -> str:
    """Push-bus topic for room-scoped resource invalidation."""
    r = str(room or "default").replace(" ", "_")
    return f"mcp.resource.{r}"


def resource_topic_for_session(session_id: str) -> str:
    """Push-bus topic for one MCP session."""
    return f"mcp.resource.session.{session_id}"


def subscribe_info(
    *,
    room: str = "",
    session_id: str = "",
    uris: Sequence[str] = (),
    sse_path_prefix: str = "/ux-channel",
) -> dict[str, Any]:
    """
    Return how a host should open SSE for resource invalidation.

    Actual stream: GET {sse_path_prefix}/mcp/resources/subscribe?topic=...
    (also works with GET {sse_path_prefix}/push/{topic} when auth allows).
    """
    topics = []
    if room:
        topics.append(resource_topic_for_room(room))
    if session_id:
        topics.append(resource_topic_for_session(session_id))
    if not topics:
        topics.append("mcp.resource.global")
    return {
        "uris": list(uris),
        "topics": topics,
        "sse": [
            f"{sse_path_prefix}/mcp/resources/subscribe?topic={t}" for t in topics
        ],
        "push": [f"{sse_path_prefix}/push/{t}" for t in topics],
        "events": ["resource.updated", "effects", "keepalive"],
    }


def publish_resource_event(
    topic: str,
    *,
    uris: Sequence[str] = (),
    reason: str = "updated",
    meta: Optional[Mapping[str, Any]] = None,
) -> int:
    """Publish a resource.updated event; returns subscriber hit count."""
    bus = get_push_bus()
    payload = {
        "event": "resource.updated",
        "uris": list(uris),
        "reason": reason,
        "meta": dict(meta or {}),
    }
    return bus.publish(topic, payload)


def publish_effects_invalidation(
    *,
    room: str = "",
    session_id: str = "",
    effects: Optional[Mapping[str, Any]] = None,
    regions: Sequence[str] = (),
) -> int:
    """After a tool call — notify resource subscribers of changed regions."""
    fx = dict(effects or {})
    regs = list(regions) or list(fx.get("regions") or [])
    uris = [f"uid://region/{u}" for u in regs]
    if room:
        uris.append(f"uid://situation/{room}")
        uris.append(f"uid://outbox/{room}")
    n = 0
    if room:
        n += publish_resource_event(
            resource_topic_for_room(room),
            uris=uris,
            reason="tool_effects",
            meta={"effects": {"regions": regs, "ok": fx.get("ok")}},
        )
    if session_id:
        n += publish_resource_event(
            resource_topic_for_session(session_id),
            uris=uris,
            reason="tool_effects",
            meta={"effects": {"regions": regs, "ok": fx.get("ok")}},
        )
    return n
