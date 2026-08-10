"""Action lifecycle hooks."""

from __future__ import annotations

from typing import Any, Callable, Optional, Protocol

from ux_channel.protocol.types import Intent, Result


class BeforeHook(Protocol):
    def __call__(self, intent: Intent, args: dict[str, Any]) -> Optional[Result]:
        """Return a Result to short-circuit, or None to continue."""
        ...


class AfterHook(Protocol):
    def __call__(self, intent: Intent, result: Result) -> Result:
        ...


class HookList:
    def __init__(self) -> None:
        self.before: list[BeforeHook] = []
        self.after: list[AfterHook] = []

    def add_before(self, fn: BeforeHook) -> BeforeHook:
        self.before.append(fn)
        return fn

    def add_after(self, fn: AfterHook) -> AfterHook:
        self.after.append(fn)
        return fn
