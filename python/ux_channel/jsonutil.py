"""JSON safety helpers (depth / breadth limits for untrusted Intent args)."""

from __future__ import annotations

from typing import Any


class JsonLimitError(ValueError):
    pass


def check_json_limits(
    value: Any,
    *,
    max_depth: int = 12,
    max_keys: int = 200,
    max_list: int = 500,
    _depth: int = 0,
) -> None:
    """Raise JsonLimitError if structure is too deep or wide (DoS guard)."""
    if _depth > max_depth:
        raise JsonLimitError(f"JSON depth exceeds {max_depth}")
    if isinstance(value, dict):
        if len(value) > max_keys:
            raise JsonLimitError(f"JSON object exceeds {max_keys} keys")
        for v in value.values():
            check_json_limits(
                v, max_depth=max_depth, max_keys=max_keys, max_list=max_list, _depth=_depth + 1
            )
    elif isinstance(value, (list, tuple)):
        if len(value) > max_list:
            raise JsonLimitError(f"JSON array exceeds {max_list} items")
        for v in value:
            check_json_limits(
                v, max_depth=max_depth, max_keys=max_keys, max_list=max_list, _depth=_depth + 1
            )
