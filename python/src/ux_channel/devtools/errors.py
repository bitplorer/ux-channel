"""
Developer tooling / CLI exceptions — cognitively consistent, never silent failures.

Every user-facing failure is a :class:`DxError` with:

* ``code`` — stable machine id (``bridge.contract_not_found``)
* ``message`` — what happened
* ``hint`` — what to do next
* ``exit_code`` — process status for the CLI
"""

from __future__ import annotations

from typing import Any, Optional

from ux_channel.protocol.errors import ChannelError

__all__ = [
    "DxError",
    "DxUsageError",
    "DxNotFoundError",
    "DxConflictError",
    "DxValidationError",
    "DxInternalError",
]


class DxError(ChannelError):
    """Base DX error — always loggable, always actionable."""

    code: str = "dx.error"
    exit_code: int = 1
    level: str = "error"  # error | warning (rare)

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        hint: str = "",
        details: Any = None,
        exit_code: Optional[int] = None,
    ) -> None:
        self.message = message
        if code is not None:
            self.code = code
        self.hint = hint or ""
        self.details = details
        if exit_code is not None:
            self.exit_code = exit_code
        super().__init__(message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "details": self.details,
            "exit_code": self.exit_code,
            "level": self.level,
        }


class DxUsageError(DxError):
    """Bad CLI args / missing required operands."""

    code = "dx.usage"
    exit_code = 2

    def __init__(self, message: str, *, hint: str = "", **kw: Any) -> None:
        super().__init__(message, hint=hint or "ux_channel --help", **kw)


class DxNotFoundError(DxError):
    """Missing file, package, method, recipe, …"""

    code = "dx.not_found"
    exit_code = 3


class DxConflictError(DxError):
    """Idempotent conflict — needs --force or remove first."""

    code = "dx.conflict"
    exit_code = 4


class DxValidationError(DxError):
    """Contract / config / arg validation failed."""

    code = "dx.validation"
    exit_code = 1


class DxInternalError(DxError):
    """Unexpected failure — bug or environment."""

    code = "dx.internal"
    exit_code = 1
