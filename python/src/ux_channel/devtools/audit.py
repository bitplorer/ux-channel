"""
Audit — intent log + forensics as one attach.

* **Public product façade:** ``attach_audit`` / ``AuditBundle`` (root export).
* Implementation modules load only when attach runs (import weight).
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = ["attach_audit", "AuditBundle"]


class AuditBundle:
    """Paired intent log + forensic store (public)."""

    def __init__(self, log: Any, forensics: Any) -> None:
        self.log = log
        self.forensics = forensics

    def export(self, *, since: int = 0) -> dict[str, Any]:
        return {
            "intents": [e.to_dict() for e in self.log.since(since)],
            "frames": [f.to_dict() for f in self.forensics.since(since)],
        }


def attach_audit(
    channel: Any,
    *,
    redis_url: Optional[str] = None,
    intent_log: Any = None,
    forensics: Any = None,
) -> AuditBundle:
    """Wire intent log + forensic morph capture on one channel (public)."""
    from ux_channel.devtools.forensics import attach_forensics
    from ux_channel.devtools.intent_log import attach_intent_log

    if intent_log is None and redis_url:
        log = attach_intent_log(channel, redis_url=redis_url)
    elif intent_log is not None:
        log = attach_intent_log(channel, log=intent_log)
    else:
        log = attach_intent_log(channel)

    store = attach_forensics(channel, store=forensics)
    bag = AuditBundle(log, store)
    channel.audit = bag
    return bag
