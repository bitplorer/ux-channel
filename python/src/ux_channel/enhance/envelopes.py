"""Result envelope helpers — attach optional keys; strip for classic peers."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ux_channel.enhance.continuations import Continuation, attach_continuations
from ux_channel.enhance.causal import Trace, attach_trace

OPTIONAL_RESULT_KEYS = frozenset(
    {
        "continuations",
        "trace",
        "receipt",
        "surfaces",
        "perception",
    }
)


def enhance_result(
    result_dict: dict[str, Any],
    *,
    continuations: Sequence[Continuation | Mapping[str, Any]] | None = None,
    trace: Trace | Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(result_dict)
    if continuations:
        out = attach_continuations(out, continuations)
    if trace is not None:
        out = attach_trace(out, trace)
    if extra:
        for k, v in extra.items():
            if v is not None:
                out[k] = v
    return out


def strip_unknown_for_classic(result_dict: Mapping[str, Any]) -> dict[str, Any]:
    """Project to classic floor (v, ok, ops, error?, meta?)."""
    keep = {"v", "ok", "ops", "error", "meta"}
    return {k: v for k, v in result_dict.items() if k in keep}
