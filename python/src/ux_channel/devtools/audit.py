"""
Audit — intent log + forensics as one attach.

=================================================================
PUBLIC / PRIVATE
=================================================================
* **Public product façade:** ``attach_audit`` / ``AuditBundle`` (root export).
* **Implementation:** ``ux_channel.intent_log`` + ``ux_channel.forensics``.
* Prefer this module over teaching raw log/forensics attach helpers in app docs.
"""

from __future__ import annotations

from typing import Any, Optional

from ux_channel.devtools.forensics import ForensicStore, MemoryForensicStore, attach_forensics
from ux_channel.devtools.intent_log import MemoryIntentLog, attach_intent_log

__all__ = ["attach_audit", "AuditBundle"]


class AuditBundle:
    """Paired intent log + forensic store (public)."""

    def __init__(self, log: Any, forensics: ForensicStore) -> None:
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
    forensics: Optional[ForensicStore] = None,
) -> AuditBundle:
    """
    Wire intent log + forensic morph capture on one channel (public).

    ::

        audit = attach_audit(ch)
        pack = audit.export()
    """
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
