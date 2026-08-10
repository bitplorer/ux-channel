"""
Action catalog — machine-readable registry metadata for docs / codegen / OpenAPI.
"""

from __future__ import annotations

import inspect
from typing import Any

from ux_channel.host.registry import ActionRegistry


def action_catalog(registry: ActionRegistry) -> list[dict[str, Any]]:
    """
    Describe registered actions: name, sync/async, parameter names (no defaults secrets).
    """
    out: list[dict[str, Any]] = []
    for name in registry.names():
        fn = registry.get(name)
        if fn is None:
            continue
        sig = inspect.signature(fn)
        params = []
        for pname, param in sig.parameters.items():
            if pname == "ctx":
                continue
            params.append(
                {
                    "name": pname,
                    "kind": str(param.kind).split(".")[-1],
                    "required": param.default is inspect.Parameter.empty
                    and param.kind
                    not in (
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    ),
                    "annotation": (
                        None
                        if param.annotation is inspect.Parameter.empty
                        else getattr(param.annotation, "__name__", str(param.annotation))
                    ),
                }
            )
        out.append(
            {
                "name": name,
                "async": inspect.iscoroutinefunction(fn),
                "params": params,
                "doc": (inspect.getdoc(fn) or "").split("\n")[0][:200],
            }
        )
    return out
