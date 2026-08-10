"""
Policy hooks — optional allow/deny for actions and topics (Wave 5).

USAGE
-----
::

    from ux_channel.security.policy import PolicyEngine, get_policy, set_policy

    eng = PolicyEngine()
    eng.allow_action(lambda intent, principal: principal is not None)
    eng.allow_topic(lambda topic, principal: topic.startswith("public.") or principal)
    set_policy(eng)
"""

from __future__ import annotations

import threading
from typing import Any, Callable, List, Optional, Tuple

ActionRule = Callable[[Any, Any], bool]
TopicRule = Callable[[str, Any], bool]


class PolicyEngine:
    def __init__(self) -> None:
        self._action_rules: List[ActionRule] = []
        self._topic_rules: List[TopicRule] = []

    def allow_action(self, rule: ActionRule) -> None:
        self._action_rules.append(rule)

    def allow_topic(self, rule: TopicRule) -> None:
        self._topic_rules.append(rule)

    def check_action(self, intent: Any, principal: Any = None) -> Tuple[bool, str]:
        for rule in self._action_rules:
            try:
                if not rule(intent, principal):
                    return False, "policy denied action"
            except Exception as exc:  # noqa: BLE001
                return False, f"policy error: {type(exc).__name__}"
        return True, "ok"

    def check_topic(self, topic: str, principal: Any = None) -> Tuple[bool, str]:
        for rule in self._topic_rules:
            try:
                if not rule(topic, principal):
                    return False, "policy denied topic"
            except Exception as exc:  # noqa: BLE001
                return False, f"policy error: {type(exc).__name__}"
        return True, "ok"


_engine: Optional[PolicyEngine] = None
_lock = threading.Lock()


def get_policy() -> Optional[PolicyEngine]:
    return _engine


def set_policy(engine: Optional[PolicyEngine]) -> None:
    global _engine
    with _lock:
        _engine = engine
