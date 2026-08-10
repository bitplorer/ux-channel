"""Pydantic-validated actions (optional; requires pydantic v2)."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Optional, Type

from ux_channel.protocol.errors import ActionError
from ux_channel.host.registry import ActionRegistry


def pydantic_action(
    registry: ActionRegistry,
    name: str,
    model: Type[Any],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Register an action that validates Intent args/form into a Pydantic model.

    Usage::

        class PlaceIn(BaseModel):
            item_id: str
            qty: int = 1

        @pydantic_action(reg, \"Orders.place\", PlaceIn)
        async def place(data: PlaceIn, ctx: ActionContext):
            ...
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(**kwargs: Any) -> Any:
            # strip ctx for model
            ctx = kwargs.pop("ctx", None)
            try:
                data = model.model_validate(kwargs)
            except Exception as exc:
                # pydantic ValidationError
                fields: dict[str, list[str]] = {}
                err = getattr(exc, "errors", None)
                if callable(err):
                    for e in err():
                        loc = ".".join(str(x) for x in e.get("loc", ()))
                        fields.setdefault(loc or "_", []).append(e.get("msg", "invalid"))
                raise ActionError("validation", "Invalid input", fields=fields or None) from exc
            # call original with data= and optional ctx=
            sig = inspect.signature(fn)
            call: dict[str, Any] = {}
            if "data" in sig.parameters:
                call["data"] = data
            else:
                # expand fields
                call.update(data.model_dump())
            if "ctx" in sig.parameters and ctx is not None:
                call["ctx"] = ctx
            if inspect.iscoroutinefunction(fn):
                return await fn(**call)
            return fn(**call)

        # preserve name for registry
        wrapper.__name__ = fn.__name__
        wrapper.__annotations__ = {"return": Any}
        registry.register(name, wrapper)
        return fn

    return decorator
