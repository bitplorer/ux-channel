"""Shared factory + commit helpers for bridge presets."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ux_channel.render.placement import Placement


class BridgeFactoryMixin:
    """
    ChartBridge-style DX for any package::

        fx = ConfettiBridge(ch)
        burst = fx("hero")
        return burst.commit()
    """

    package: str = ""
    methods: tuple[str, ...] = ("update", "destroy")
    description: str = ""

    def __init__(self, ch: Any, id: str | None = None, **kwargs: Any) -> None:
        if ch is None:
            raise ValueError(f"{type(self).__name__} requires a Channel (Channel.boot)")
        self.ch = ch
        auto_register = kwargs.pop("auto_register", True)
        self._defaults = {k: v for k, v in kwargs.items() if v is not None}
        if id is None:
            self.id = ""
            self._factory = True
            self._state = self._new_state(**self._defaults)
            return
        if not str(id).strip():
            raise ValueError(
                f"{type(self).__name__} island id required; "
                f"use {type(self).__name__}(ch) then factory('id', …)"
            )
        self._factory = False
        self.id = str(id).strip()
        self._state = self._new_state(**self._defaults)
        if auto_register:
            self.register()

    def _new_state(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    def __call__(self, id: str, **kwargs: Any) -> Any:
        if not id or not str(id).strip():
            raise ValueError("island id is required")
        base = dict(getattr(self, "_defaults", {}) or {})
        # include current factory state as defaults when present
        if hasattr(self, "_state") and hasattr(self._state, "__dict__"):
            for k, v in vars(self._state).items():
                if k.startswith("_"):
                    continue
                if k not in base and v not in (None, "", [], {}):
                    base[k] = v
        base.update(kwargs)
        return type(self)(self.ch, str(id).strip(), auto_register=True, **base)

    def _require_island(self) -> None:
        if getattr(self, "_factory", False) or not self.id:
            raise TypeError(
                f"{type(self).__name__} is a factory — create an island first: "
                f"fx = {type(self).__name__}(ch); item = fx('id', …)"
            )

    def register(self) -> Any:
        self.ch.bridge.register(
            self.package,
            methods=self.methods,
            description=self.description or f"{type(self).__name__} preset",
        )
        return self

    def props(self) -> dict[str, Any]:
        self._require_island()
        return self._build_props()

    def _build_props(self) -> dict[str, Any]:
        raise NotImplementedError

    def mount_attrs(
        self,
        *,
        class_name: str = "",
        style: str = "",
        css: Mapping[str, str] | None = None,
        **extra: str,
    ) -> dict[str, str]:
        """Attrs for the mount element (underscore keys for Python HTML DSLs)."""
        spec = self.mount_spec(class_name=class_name, style=style, css=css)
        out = dict(spec.attrs_py)
        for k, v in extra.items():
            out[str(k).replace("-", "_")] = v
        return out

    def mount_spec(
        self,
        *,
        class_name: str = "",
        style: str = "",
        css: Mapping[str, str] | None = None,
    ) -> Placement:
        self._require_island()
        return self.ch.bridge.mount_spec(
            self.id,
            package=self.package,
            props=self.props(),
            class_name=class_name,
            style=style,
            css=css,
        )

    def mount_ops(self) -> list:
        self._require_island()
        return self.ch.bridge.mount_ops(self.id, self.package, props=self.props())

    def update_ops(self) -> list:
        self._require_island()
        return self.ch.bridge.update_ops(self.id, self.props())

    def call_ops(self, method: str, *args: Any) -> list:
        self._require_island()
        return self.ch.bridge.call(self.id, method, *args, package=self.package)

    def _result_with_ops(self, ops: list, *, notice: str | None = None) -> Any:
        from ux_channel.protocol.types import Result

        base = self.ch.done(notice=notice) if notice else self.ch.done()
        return Result(
            ok=True,
            ops=list(base.ops or []) + list(ops),
            meta=dict(base.meta or {}),
            v=getattr(base, "v", None) or "1",
        )

    def commit(self, **props: Any) -> Any:
        self._require_island()
        notice = props.pop("notice", None)
        if props:
            self.configure(**props)
        return self._result_with_ops(self.update_ops(), notice=notice)

    def commit_mount(self, *, notice: str | None = None) -> Any:
        return self._result_with_ops(self.mount_ops(), notice=notice)

    def fire(self, method: str, *args: Any, notice: str | None = None) -> Any:
        """call method + success Result (effects: burst, celebrate, …)."""
        return self._result_with_ops(self.call_ops(method, *args), notice=notice)

    def configure(self, **kwargs: Any) -> Any:
        self._require_island()
        st = self._state
        for k, v in kwargs.items():
            if v is None:
                continue
            if hasattr(st, k):
                setattr(st, k, v)
        return self

    def describe(self) -> dict[str, Any]:
        if getattr(self, "_factory", False):
            return {
                "mode": "factory",
                "package": self.package,
                "class": type(self).__name__,
            }
        return {
            "mode": "island",
            "id": self.id,
            "package": self.package,
            "props": self.props(),
            "class": type(self).__name__,
        }

    def __repr__(self) -> str:
        if getattr(self, "_factory", False):
            return f"{type(self).__name__}(factory)"
        return f"{type(self).__name__}(id={self.id!r})"
