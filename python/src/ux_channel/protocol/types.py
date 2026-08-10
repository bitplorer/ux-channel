"""Protocol types: Intent (request) and Result (response).
ux-channel's wire language is deliberately small and versioned:
  Intent  — client names an action + args + capability
  Result  — server returns ordered apply ops (+ error/meta)
These types are the **contract** shared by Python encode/dispatch, host
adapters, tests, and the browser runtime (ux-channel.js). Keeping them
dependency-free…"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Optional, Sequence

# Major protocol version embedded in every Intent/Result.
# Additive op types do not bump this; breaking wire changes must.
PROTOCOL_VERSION = "1"


def _strip_none(data: Mapping[str, Any]) -> dict[str, Any]:
    """Omit null optional fields for compact JSON (matches RESULT.md)."""
    return {k: v for k, v in data.items() if v is not None}


@dataclass
class ErrorObject:
    """
    Structured action failure carried alongside optional UI ops.

    Designed so validation can both set ``ok=false`` and morph the form
    highlighting errors — not just return HTTP 400 with no UI.
    """

    code: str
    message: str
    fields: Optional[dict[str, list[str]]] = None
    retryable: Optional[bool] = None
    details: Any = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "code": self.code,
                "message": self.message,
                "fields": self.fields,
                "retryable": self.retryable,
                "details": self.details,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ErrorObject":
        return cls(
            code=str(data["code"]),
            message=str(data["message"]),
            fields=data.get("fields"),
            retryable=data.get("retryable"),
            details=data.get("details"),
        )


@dataclass
class Intent:
    """
    Client → server invocation of a named action.

    Fields map 1:1 to RESULT.md / JSON Schema. ``form`` holds progressive
    enhance / FormData fields; they fill missing ``args`` keys at dispatch
    without being required in the capability args hash (by default).
    """

    action: str
    args: dict[str, Any] = field(default_factory=dict)
    cap: Optional[str] = None
    target: Optional[str] = None
    request_id: Optional[str] = None
    form: Optional[dict[str, Any]] = None
    accept_stream: bool = False
    idempotency_key: Optional[str] = None
    meta: Optional[dict] = None
    v: str = PROTOCOL_VERSION  # protocol version — NOT a region id

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "v": self.v,
                "action": self.action,
                "args": self.args or None,
                "cap": self.cap,
                "target": self.target,
                "request_id": self.request_id,
                "form": self.form,
                "accept_stream": self.accept_stream or None,
                "idempotency_key": self.idempotency_key,
                "meta": self.meta,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Intent":
        ver = str(data.get("v", PROTOCOL_VERSION))
        if ver.split(".")[0] != PROTOCOL_VERSION:
            raise ValueError(f"unsupported protocol v={ver!r}")
        if "action" not in data:
            raise ValueError("intent.action is required")
        return cls(
            v=PROTOCOL_VERSION,
            action=str(data["action"]),
            args=dict(data.get("args") or {}),
            cap=data.get("cap"),
            target=data.get("target"),
            request_id=data.get("request_id"),
            form=dict(data["form"]) if data.get("form") else None,
            accept_stream=bool(data.get("accept_stream", False)),
            idempotency_key=data.get("idempotency_key"),
            meta=data.get("meta"),
        )


@dataclass
class Result:
    """
    Server → client apply payload (the unit of UI truth after an action).

    First principles
    ----------------
    The browser never trusts free-form server HTML outside **ops**. A Result
    says: apply these instructions in order; if ``ok`` is false, still apply
    ops (e.g. re-morph a form) and surface ``error``.

    Fields
    ------
    ops:
        Ordered apply instructions (morph, toast, bridge.*, …).
    ok:
        False when the action failed; HTTP status maps from ``error.code``.
    error:
        ``ErrorObject`` with stable ``code`` (see ``error_map``).
    meta:
        Diagnostics and protocol extras (``request_id``, ``retry_after``,
        ``error_kind``, ``refresh_errors``, …). Never put secrets here.

    Constructors
    ------------
    ``Result.success(...)`` — success
    ``Result.failure(...)`` — failure

    Empty ``ops`` with ``ok=True`` is a valid no-op success.
    """

    ops: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = True
    error: Optional[ErrorObject] = None
    meta: dict[str, Any] = field(default_factory=dict)
    v: str = PROTOCOL_VERSION  # protocol version — NOT a region id

    @classmethod
    def success(
        cls, *ops: Mapping[str, Any] | Sequence[Mapping[str, Any]], **meta: Any
    ) -> "Result":
        """
        Build a successful Result from one or more op dicts.

        Also accepts a nested sequence of ops for helpers that return list[Op]::

            Result.success(*mount_ops(...), toast(\"ok\"))
        """
        flat: list[dict[str, Any]] = []
        for item in ops:
            if isinstance(item, Mapping) and "op" in item:
                flat.append(dict(item))
            elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
                for sub in item:
                    flat.append(dict(sub))
            else:
                raise TypeError(f"expected op mapping, got {type(item)!r}")
        return cls(ok=True, ops=flat, meta=dict(meta) if meta else {})

    @classmethod
    def failure(
        cls,
        code: str,
        message: str,
        *ops: Mapping[str, Any],
        **meta: Any,
    ) -> "Result":
        """
        Build ok=false Result; ops may still update UI (e.g. re-render form).

        Keyword ``fields`` / ``retryable`` go into ErrorObject; remaining kwargs
        become Result.meta (typed as **Any so call sites stay mypy-clean).
        """
        fields = meta.pop("fields", None)
        retryable = meta.pop("retryable", None)
        return cls(
            ok=False,
            error=ErrorObject(
                code=code, message=message, fields=fields, retryable=retryable
            ),
            ops=[dict(o) for o in ops],
            meta=dict(meta) if meta else {},
        )

    def to_dict(self) -> dict[str, Any]:
        body: MutableMapping[str, Any] = {
            "v": self.v,
            "ok": self.ok,
            "ops": self.ops,
        }
        if self.error is not None:
            body["error"] = self.error.to_dict()
        if self.meta:
            body["meta"] = self.meta
        return dict(body)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Result":
        err = data.get("error")
        ver = str(data.get("v", PROTOCOL_VERSION))
        if ver.split(".")[0] != PROTOCOL_VERSION:
            raise ValueError(f"unsupported protocol v={ver!r}")
        return cls(
            v=PROTOCOL_VERSION,
            ok=bool(data.get("ok", True)),
            ops=[dict(o) for o in (data.get("ops") or [])],
            error=ErrorObject.from_dict(err) if err else None,
            meta=dict(data.get("meta") or {}),
        )


# Prefer Result.success(...) in typed call sites.
