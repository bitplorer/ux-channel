"""Structured Op algebra (Wave A) \u2014 host composition language.

Wire floor stays classic ``{\"op\": \"...\"}`` dicts.
This package is composition-only: never required for interop.

Example::

    from ux_channel.ops import Op, plan, to_classic, macros

    ops = plan(Op.toast(\"ok\"), Op.morph(\"#badge\", html))
    result_ops = to_classic(ops)  # -> Result.ops
"""
from __future__ import annotations

from ux_channel.ops.catalog import Op, plan, as_wire
from ux_channel.ops.translate import from_classic, to_classic
from ux_channel.ops import macros

__all__ = [
    "Op",
    "plan",
    "as_wire",
    "from_classic",
    "to_classic",
    "macros",
]
