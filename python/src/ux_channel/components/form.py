"""Validated form component — fields, errors, focus, toast."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from ux_channel.components.base import ChannelComponent
from ux_channel.render.html_safe import esc
from ux_channel.protocol.types import Result

Validator = Callable[[dict[str, str]], dict[str, list[str]]]
SubmitHandler = Callable[[dict[str, str]], Result | dict[str, Any] | None]


@dataclass
class Field:
    name: str
    label: str
    type: str = "text"
    required: bool = False
    placeholder: str = ""
    autocomplete: str = ""


class Form(ChannelComponent):
    """
    Drop-in form with server validation pattern.

    ::

        form = Form(ch, uid="Login:root", fields=[
            Field("email", "Email", type="email", required=True),
            Field("password", "Password", type="password", required=True),
        ], validate=my_validate, on_submit=my_submit).install()
    """

    kind = "Form"

    def __init__(
        self,
        channel,
        *,
        uid: str | None = None,
        name: str = "Form",
        fields: list[Field] | None = None,
        validate: Validator | None = None,
        on_submit: SubmitHandler | None = None,
        submit_label: str = "Submit",
        success_redirect: str | None = None,
    ):
        super().__init__(channel, uid=uid, name=name)
        self.fields = fields or []
        self.validate = validate
        self.on_submit = on_submit
        self.submit_label = submit_label
        self.success_redirect = success_redirect

    def render(self, **state: Any) -> str:
        from ux_channel.render.html import form_open

        values: dict[str, str] = dict(state.get("values") or {})
        errors: dict[str, list[str]] = dict(state.get("errors") or {})
        action = self.action_name("submit")
        cap = None
        try:
            cap = self.ch.mint(action, {})
        except Exception:
            cap = None
        open_tag = form_open(
            action,
            cap=cap,
            uid_id=self.uid,
            target=self.uid,
            class_name="ux-form",
            style="display:grid;gap:.75rem;max-width:22rem",
        )
        rows = []
        for f in self.fields:
            err = (errors.get(f.name) or [""])[0] or None
            val = values.get(f.name, "")
            aria = ' aria-invalid="true"' if err else ""
            req = " required" if f.required else ""
            if err:
                err_html = (
                    f'<p data-channel-error="{esc(f.name)}" '
                    f'style="color:#b91c1c;font-size:.85rem">{esc(err)}</p>'
                )
            else:
                err_html = f'<p data-channel-error="{esc(f.name)}" hidden></p>'
            rows.append(
                f'<label class="ux-field">{esc(f.label)}'
                f'<input id="{esc(f.name)}" name="{esc(f.name)}" type="{esc(f.type)}" '
                f'value="{esc(val)}" placeholder="{esc(f.placeholder)}"'
                f"{req}{aria} "
                f'style="display:block;width:100%;margin-top:.25rem;padding:.5rem"/>'
                f"{err_html}</label>"
            )
        rows.append(
            f'<button type="submit" class="ux-submit">{esc(self.submit_label)}</button>'
        )
        return open_tag + "\n" + "\n".join(rows) + "\n</form>"

    def _register(self) -> None:
        comp = self

        @self.ch.action(self.action_name("submit"))
        def submit(**kwargs: Any) -> Result:
            values = {f.name: str(kwargs.get(f.name, "") or "") for f in comp.fields}
            errors: dict[str, list[str]] = {}
            if comp.validate:
                errors = comp.validate(values) or {}
            else:
                for f in comp.fields:
                    if f.required and not values.get(f.name):
                        errors.setdefault(f.name, []).append("Required")
            if errors:
                focus_target = f"#{next(iter(errors))}"
                fail = getattr(comp.ch, "fail", None)
                if fail is not None and hasattr(fail, "valid"):
                    return fail.valid(
                        errors,
                        region=comp.uid,
                        html=comp.render(values=values, errors=errors),
                        focus=focus_target,
                    )
                return comp.ch.invalid(
                    errors,
                    region=comp.uid,
                    html=comp.render(values=values, errors=errors),
                    focus_target=focus_target,
                )
            if comp.on_submit:
                out = comp.on_submit(values)
                if isinstance(out, Result):
                    return out
            if comp.success_redirect:
                return comp.ch.redirect(comp.success_redirect)  # type: ignore[return-value]
            return comp.refresh(
                values=values, errors={}, notice="Saved", notice_level="success"
            )
