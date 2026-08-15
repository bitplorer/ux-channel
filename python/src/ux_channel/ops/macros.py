"""Host-only macros — expand to list[Op]; never appear on the wire."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ux_channel.ops.catalog import Op, plan


def restart_timer(timer_id: str, ms: int) -> list[Op]:
    return plan(Op.timer_clear(timer_id), Op.timer_set(timer_id, ms))


def set_loading(region: str, busy: bool = True, status: str | None = None) -> list[Op]:
    ops = [Op.busy(region, busy)]
    if status is not None:
        ops.append(Op.set_text(f"{region}-status", status))
    return ops


def form_errors(form_id: str, errors: Mapping[str, str]) -> list[Op]:
    ops: list[Op] = []
    for field, msg in errors.items():
        ops.append(Op.set_text(f"{form_id}.{field}-error", msg))
        ops.append(Op.set_attr(f"{form_id}.{field}", {"aria-invalid": "true"}))
    if errors:
        first = next(iter(errors))
        ops.append(Op.focus(f"{form_id}.{first}"))
    return ops


def clear_form_errors(form_id: str, fields: Sequence[str]) -> list[Op]:
    ops: list[Op] = []
    for field in fields:
        ops.append(Op.set_text(f"{form_id}.{field}-error", ""))
        ops.append(Op.set_attr(f"{form_id}.{field}", {"aria-invalid": "false"}))
    return ops


def navigate_to(path: str, *, title: str | None = None, replace: bool = False) -> list[Op]:
    op = Op.navigate(path, replace=replace)
    return plan(op)


def toast_ok(message: str) -> list[Op]:
    return plan(Op.toast(message, level="success"))


def toast_err(message: str) -> list[Op]:
    return plan(Op.toast(message, level="error"))
