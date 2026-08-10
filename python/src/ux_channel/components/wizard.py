"""Wizard — multi-step flow with next/back/finish."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from ux_channel.components.base import ChannelComponent
from ux_channel.render.html_safe import esc
from ux_channel.protocol.ops import push_url
from ux_channel.protocol.types import Result

StepValidator = Callable[[int, dict[str, Any]], dict[str, list[str]]]
StepRenderer = Callable[[int, dict[str, Any], dict[str, list[str]]], str]


@dataclass
class Step:
    title: str
    fields: list[str]


class Wizard(ChannelComponent):
    """
    ::

        w = Wizard(ch, uid="Onboard:wiz", steps=[
            Step("Account", ["email"]),
            Step("Profile", ["name"]),
        ], render_step=my_render, validate_step=my_validate,
           on_finish=lambda data: ch.redirect("/done")).install()
    """

    kind = "Wizard"

    def __init__(
        self,
        channel,
        *,
        uid: str | None = None,
        name: str = "Wizard",
        steps: list[Step] | None = None,
        render_step: StepRenderer | None = None,
        validate_step: StepValidator | None = None,
        on_finish: Callable[[dict[str, Any]], Result] | None = None,
        path_prefix: str = "",
    ):
        super().__init__(channel, uid=uid, name=name)
        self.steps = steps or []
        self.render_step = render_step
        self.validate_step = validate_step
        self.on_finish = on_finish
        self.path_prefix = path_prefix

    def render(self, **state: Any) -> str:
        step = int(state.get("step", 0) or 0)
        data: dict[str, Any] = dict(state.get("data") or {})
        errors: dict[str, list[str]] = dict(state.get("errors") or {})
        total = len(self.steps) or 1
        step = max(0, min(step, total - 1))
        title = self.steps[step].title if self.steps else f"Step {step + 1}"
        body = (
            self.render_step(step, data, errors)
            if self.render_step
            else f"<p>{esc(title)}</p>"
        )
        nav = []
        if step > 0:
            nav.append(self.btn("Back", "back", trust={"step": step, **{k: data.get(k, "") for k in (self.steps[step].fields if self.steps else [])}}, class_name="ux-wiz-back"))
        is_last = step >= total - 1
        nav.append(
            self.btn(
                "Finish" if is_last else "Next",
                "next",
                trust={"step": step},
                class_name="ux-wiz-next",
            )
        )
        header = (
            f'<div class="ux-wiz-header" style="margin-bottom:.75rem">'
            f"<strong>Step {step + 1}/{total}: {esc(title)}</strong></div>"
        )
        return self.wrap(
            header + f'<div class="ux-wiz-body">{body}</div>'
            f'<div class="ux-wiz-nav" style="display:flex;gap:.5rem;margin-top:1rem">{"".join(nav)}</div>',
            class_="ux-wizard",
        )

    def _register(self) -> None:
        comp = self

        @self.ch.action(self.action_name("next"))
        def next_step(step: int = 0, **fields: Any) -> Result:
            data = dict(fields)
            step = int(step or 0)
            errors: dict[str, list[str]] = {}
            if comp.validate_step:
                errors = comp.validate_step(step, data) or {}
            if errors:
                return comp.ch.fail.valid(
                    errors,
                    region=comp.uid,
                    html=comp.render(step=step, data=data, errors=errors),
                    focus=f"#{next(iter(errors))}",
                )
            total = len(comp.steps) or 1
            if step >= total - 1:
                if comp.on_finish:
                    return comp.on_finish(data)
                return comp.refresh(step=step, data=data, notice="Done", notice_level="success")
            new_step = step + 1
            html = comp.render(step=new_step, data=data, errors={})
            b = comp.ch.ui.region(comp.uid, html)
            if comp.path_prefix:
                b.push_url(f"{comp.path_prefix}?step={new_step}")
            return b.ok()

        @self.ch.action(self.action_name("back"))
        def back(step: int = 1, **fields: Any) -> Result:
            data = dict(fields)
            new_step = max(0, int(step or 1) - 1)
            html = comp.render(step=new_step, data=data, errors={})
            b = comp.ch.ui.region(comp.uid, html)
            if comp.path_prefix:
                b.push_url(f"{comp.path_prefix}?step={new_step}")
            return b.ok()
