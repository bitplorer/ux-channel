"""
Generic island bridge — wrap **any** npm / adapter package for any HTML host.

Use when there is no dedicated preset yet::

    from ux_channel.bridges import GenericBridge

    widgets = GenericBridge(ch, package="my-lib", methods=("update", "destroy", "focus"))
    editor = widgets("ed1", props={"theme": "dark", "value": "hi"})
    return editor.commit(props={"value": "bye"})

    # host:
    #   Div(**editor.mount_spec(class_name="h-64").attrs_py)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ux_channel.bridges._factory import BridgeFactoryMixin
from ux_channel.render.placement import Placement

__all__ = ["GenericBridge"]


@dataclass
class _State:
    props: dict[str, Any] = field(default_factory=dict)


class GenericBridge(BridgeFactoryMixin):
    """
    Package-agnostic factory. Props pass through to the adapter unchanged.
    """

    def __init__(
        self,
        ch: Any,
        id: str | None = None,
        *,
        package: str = "",
        methods: Sequence[str] = ("update", "destroy"),
        props: Mapping[str, Any] | None = None,
        description: str = "",
        auto_register: bool = True,
    ) -> None:
        # package/methods must be set before super (register)
        if not package and id is None and not getattr(self, "package", ""):
            # factory without package yet — allow GenericBridge(ch) then re-bind
            pass
        self.package = str(package or getattr(self, "package", "") or "")
        self.methods = tuple(methods) if methods else ("update", "destroy")
        self.description = description or f"Generic bridge ({self.package or 'unset'})"
        # When used as factory: GenericBridge(ch, package="x")
        # When island: GenericBridge(ch, "id", package="x", props=...)
        super().__init__(
            ch,
            id,
            props=dict(props or {}),
            auto_register=auto_register and bool(self.package) and id is not None,
        )
        # factory may set package without id
        if id is None and self.package:
            # register package allowlist early for DX
            try:
                self.ch.bridge.register(
                    self.package, methods=self.methods, description=self.description
                )
            except Exception:
                pass

    def _new_state(self, **kwargs: Any) -> _State:
        props = kwargs.get("props") or {}
        # allow flat kwargs as props for ergonomics (except reserved)
        reserved = {"auto_register", "package", "methods", "description", "props"}
        extra = {k: v for k, v in kwargs.items() if k not in reserved and v is not None}
        merged = dict(props)
        merged.update(extra)
        return _State(props=merged)

    def __call__(self, id: str, **kwargs: Any) -> "GenericBridge":
        if not self.package and not kwargs.get("package"):
            raise ValueError(
                "GenericBridge requires package=… "
                "e.g. GenericBridge(ch, package='codemirror')('ed1', value='…')"
            )
        package = kwargs.pop("package", self.package)
        methods = kwargs.pop("methods", self.methods)
        description = kwargs.pop("description", self.description)
        props = kwargs.pop("props", None)
        if props is None:
            props = dict(kwargs)
            kwargs = {}
        else:
            props = dict(props)
            props.update(kwargs)
        return GenericBridge(
            self.ch,
            str(id).strip(),
            package=package,
            methods=methods,
            props=props,
            description=description,
            auto_register=True,
        )

    def _build_props(self) -> dict[str, Any]:
        return dict(self._state.props)

    def configure(self, **kwargs: Any) -> Any:
        self._require_island()
        if "props" in kwargs and kwargs["props"] is not None:
            self._state.props = dict(kwargs.pop("props"))
        self._state.props.update({k: v for k, v in kwargs.items() if v is not None})
        return self

    def commit(self, **props: Any) -> Any:
        self._require_island()
        notice = props.pop("notice", None)
        if props:
            if "props" in props and len(props) == 1:
                self.configure(props=props["props"])
            else:
                self.configure(**props)
        return self._result_with_ops(self.update_ops(), notice=notice)

    def mount_attrs(
        self,
        *,
        class_name: str = "",
        style: str = "",
        css: Mapping[str, str] | None = None,
        **extra: str,
    ) -> dict[str, str]:
        """
        Mount-element attribute dict (underscore keys)::

            Div(**editor.mount_attrs(class_name="h-80 rounded-xl"))
        """
        spec = self.mount_spec(class_name=class_name, style=style, css=css)
        out = dict(spec.attrs_py)
        for k, v in extra.items():
            out[k.replace("-", "_")] = v
        return out
