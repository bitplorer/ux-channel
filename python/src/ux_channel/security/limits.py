"""Result size / safety limits."""

from __future__ import annotations

def _serde():
    from ux_channel.protocol import serde as _m
    return _m



from typing import Any, Optional

from ux_channel.protocol.types import Result

# Defaults: generous but prevent accidental multi‑MB HTML payloads
DEFAULT_MAX_HTML_BYTES = 512_000
DEFAULT_MAX_OPS = 64
DEFAULT_MAX_RESULT_BYTES = 1_000_000


class LimitExceeded(ValueError):
    pass


def enforce_result_limits(
    result: Result,
    *,
    max_html_bytes: int = DEFAULT_MAX_HTML_BYTES,
    max_ops: int = DEFAULT_MAX_OPS,
    max_result_bytes: int = DEFAULT_MAX_RESULT_BYTES,
) -> Result:
    """
    Validate Result size. Raises LimitExceeded if over budget.
    Does not mutate ops content except refusing oversized HTML.
    """
    if len(result.ops) > max_ops:
        raise LimitExceeded(f"too many ops: {len(result.ops)} > {max_ops}")

    total_html = 0
    for i, op in enumerate(result.ops):
        html = op.get("html")
        if isinstance(html, str):
            n = len(html.encode("utf-8"))
            total_html += n
            if n > max_html_bytes:
                raise LimitExceeded(
                    f"op[{i}] html exceeds max_html_bytes ({n} > {max_html_bytes})"
                )
        # bridge props rough size
        props = op.get("props")
        if props is not None:
            import json

            try:
                pn = len(_serde().dumps(props, default=str).encode("utf-8"))
            except (TypeError, ValueError):
                pn = 0
            if pn > max_html_bytes:
                raise LimitExceeded(f"op[{i}] props exceed size limit ({pn})")

    raw = result.to_dict()
    import json

    encoded = _serde().dumps(raw, default=str).encode("utf-8")
    if len(encoded) > max_result_bytes:
        raise LimitExceeded(
            f"result JSON exceeds max_result_bytes ({len(encoded)} > {max_result_bytes})"
        )
    return result


def clamp_meta(meta: Optional[dict[str, Any]], *, max_keys: int = 32) -> dict[str, Any]:
    if not meta:
        return {}
    if len(meta) <= max_keys:
        return dict(meta)
    # keep stable subset
    keys = sorted(meta.keys())[:max_keys]
    return {k: meta[k] for k in keys}
