"""
Optional Pydantic models for OpenAPI / typed Intent-Result (extra: pydantic).

Not required at runtime — core uses dataclasses. Use when you want FastAPI
OpenAPI docs or validation on the edge.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "ux_channel.schema_models requires pydantic: pip install 'ux-channel[pydantic]'"
    ) from exc


class IntentModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    uid: str = "1"
    action: str = Field(..., min_length=1, max_length=128)
    args: dict[str, Any] = Field(default_factory=dict)
    form: Optional[dict[str, Any]] = None
    cap: Optional[str] = None
    target: Optional[str] = None
    request_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    accept_stream: bool = False
    meta: Optional[dict[str, Any]] = None


class ErrorModel(BaseModel):
    code: str
    message: str
    fields: Optional[dict[str, Any]] = None
    retryable: Optional[bool] = None


class ResultModel(BaseModel):
    uid: str = "1"
    ok: bool = True
    ops: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[ErrorModel] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ToolCallModel(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmation: Optional[str] = None
    dry_run: Optional[bool] = None
    call_id: Optional[str] = None
    idempotency_key: Optional[str] = None
