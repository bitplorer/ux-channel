"""
Bridge plane — npm **widget** hosts as **data + ops** (not HTML).

One truth
---------
* ``ch.bridge.mount_spec(...)`` → Placement / attr dict for *your* markup
* ``ch.bridge.mount_ops / update_ops / call_ops / destroy_ops`` → Result ops
* Media is **only** ``ch.media`` — not under bridge

HTML for demos: ``ux_channel.render.kit.mount_html(spec)``.
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

from typing import Any, Optional

from ux_channel.render.placement import Placement

__all__ = ["BridgePlane", "attach_bridge", "BRIDGE_PUBLIC_API"]

BRIDGE_PUBLIC_API = (
    "mount_spec",
    "mount_ops",
    "update_ops",
    "call_ops",
    "call",
    "destroy_ops",
    "register",
    "load_contract",
    "describe",
    "contract",
    "packages",
    "diagnose",
)


class BridgePlane:
    """Widget bridge façade — ops + placement data only."""

    def __init__(self, channel: Any) -> None:
        self.channel = channel

    def mount_spec(
        self,
        bridge_id: str,
        *,
        package: str,
        props: Any = None,
        tag: str = "div",
        inner: str = "",
        class_name: str = "",
        style: str = "",
        css: Any = None,
    ) -> Placement:
        """
        Placement for the **mount element** (no HTML string).

        Mount-element chrome (class/style) — for the **element**, not npm package internals::

            spec = ch.bridge.mount_spec(
                "c1", package="chart.js", props={...},
                class_name="h-80 rounded-xl",
                css={"--accent": "#4f46e5", "--track": "#1e293b"},
                style="min-height: 16rem",
            )
            # ux-dom: Div(**spec.attrs_py)  → class + style with CSS variables

        Library-specific style (Chart.js options, Leaflet pane classes) stays in
        ``props`` — only pass what that npm API understands.
        """
        import json

        from ux_channel.bridge.bridge_style import merge_host_style

        attrs = {
            "data-channel-bridge-id": str(bridge_id),
            "data-channel-bridge-package": str(package),
        }
        if class_name:
            attrs["class"] = str(class_name).strip()
        style_s = merge_host_style(style=style, css=css)
        if style_s:
            attrs["style"] = style_s

        client: dict[str, Any] = {"id": bridge_id, "package": package}
        if props is not None:
            raw = _serde.dumps(props, default=str)
            attrs["data-channel-bridge-props"] = raw
            client["props"] = props
        if class_name or style_s:
            client["host"] = {
                k: v
                for k, v in {
                    "class": class_name or None,
                    "style": style_s or None,
                    "css": dict(css) if isinstance(css, dict) else None,
                }.items()
                if v
            }
        return Placement(
            attrs=attrs,
            client=client,
            scripts=(),
            path="",
            kind="bridge-mount",
            meta={
                "tag": tag,
                "inner": inner,
                "package": package,
                "id": bridge_id,
            },
        )

    def mount_ops(
        self,
        bridge_id: str,
        package: str,
        *,
        props: Any = None,
        target: Optional[str] = None,
    ) -> list:
        from ux_channel.bridge.bridge_api import mount_ops

        return mount_ops(bridge_id, package, props=props, target=target)

    def update_ops(
        self,
        bridge_id: str,
        props: Any,
        *,
        replace: bool = False,
    ) -> list:
        from ux_channel.bridge.bridge_api import update_ops

        return update_ops(bridge_id, props, replace=replace)

    def call_ops(
        self,
        bridge_id: str,
        method: str,
        *args: Any,
        package: Optional[str] = None,
    ) -> list:
        """
        Emit ``bridge.call`` — **string method name**, not a Python callable.

        Pass ``package=`` whenever you registered a manifest so the server
        can allowlist methods (stability / safety).
        """
        from ux_channel.bridge.bridge_api import call_ops

        return call_ops(bridge_id, method, *args, package=package)

    def call(
        self,
        bridge_id: str,
        method: str,
        *args: Any,
        package: str,
        strict: bool = True,
        **kwargs: Any,
    ) -> list:
        """
        Call adapter method by **string**; validate against contract when loaded.

        * Positional *args → JSON list on the wire
        * kwargs → ordered by contract arg names when MethodSpec has names
        * No contract → allowlist methods only (register), args pass through
        """
        if not package:
            raise ValueError("package is required for ch.bridge.call (npm adapter key)")
        if kwargs and args:
            raise ValueError("pass either positional args or kwargs, not both")

        from ux_channel.bridge.bridge_contract import get_contract_registry
        from ux_channel.protocol.ops import bridge_call
        from ux_channel.bridge.plugins import get_hub

        if kwargs:
            call_args: Any = dict(kwargs)
        elif len(args) == 1 and isinstance(args[0], (list, tuple, dict)):
            call_args = args[0]
        else:
            call_args = list(args)

        # 1) Sealed protocol — fail closed when registered
        from ux_channel.bridge.bridge_protocol import get_sealed_registry

        sealed = get_sealed_registry().get(package)
        if sealed is not None:
            normalized = sealed.validate_call(method, call_args)
            get_hub().validate_bridge_call(package, method)
            return [bridge_call(bridge_id, method, normalized, package=package)]

        reg = get_contract_registry()
        contract = reg.get(package)
        if contract is not None:
            normalized = contract.validate_call(method, call_args)
        else:
            if strict:
                get_hub().validate_bridge_call(package, method)
            if call_args is None:
                normalized = []
            elif isinstance(call_args, (list, tuple)):
                normalized = list(call_args)
            elif isinstance(call_args, dict):
                normalized = [call_args]
            else:
                normalized = [call_args]
            get_hub().validate_bridge_call(package, method)

        if contract is not None:
            get_hub().validate_bridge_call(package, method)

        return [
            bridge_call(bridge_id, method, normalized, package=package)
        ]


    def _seal_package(
        self,
        package: str,
        *,
        methods: tuple | list = (),
        events: tuple | list = (),
        contract: Any = None,
    ) -> None:
        """Register sealed protocol for this package (fail-closed calls)."""
        from ux_channel.bridge.bridge_contract import MethodSpec
        from ux_channel.bridge.bridge_protocol import SealedBridgeProtocol, get_sealed_registry

        meth: dict = {}
        if contract is not None and getattr(contract, "methods", None):
            meth = dict(contract.methods)
        else:
            for m in methods or ():
                meth[str(m)] = MethodSpec(str(m))
        get_sealed_registry().register(
            SealedBridgeProtocol(
                name=str(package),
                methods=meth,
                events=frozenset(str(e) for e in (events or ())),
                package=str(package),
            )
        )

    def destroy_ops(self, bridge_id: str) -> list:

        from ux_channel.bridge.bridge_api import destroy_ops

        return destroy_ops(bridge_id)

    def register(
        self,
        package: str,
        *,
        methods: tuple[str, ...] | list[str] = (),
        events: tuple[str, ...] | list[str] = (),
        description: str = "",
        contract: Any = None,
        npm: str = "",
    ) -> Any:
        """
        Register package **contract** (methods + optional full BridgeContract).

        Client still loads the adapter via npm + ``uxBridge.register``.
        Server validates call method/args when a contract exists.
        """
        from ux_channel.bridge.bridge_api import register_simple_manifest
        from ux_channel.bridge.bridge_contract import (
            BridgeContract,
            MethodSpec,
            contract_from_mapping,
            get_contract_registry,
        )

        if contract is not None:
            if isinstance(contract, BridgeContract):
                c = contract
            elif isinstance(contract, dict):
                c = contract_from_mapping({**contract, "package": package})
            else:
                raise TypeError("contract must be BridgeContract or dict")
            get_contract_registry().add(c)
            methods = methods or c.method_names()
            events = events or c.events
            description = description or c.description
        elif methods:
            c = BridgeContract(
                package=package,
                methods={m: MethodSpec(name=m) for m in methods},
                events=tuple(events),
                description=description or f"npm bridge:{package}",
                npm=npm,
            )
            get_contract_registry().add(c)
        self._seal_package(
            package,
            methods=methods,
            events=events,
            contract=locals().get("c"),
        )
        return register_simple_manifest(
            package,
            methods=tuple(methods),
            events=tuple(events),
            description=description or f"npm bridge:{package}",
        )

    def load_contract(self, path: str | Any) -> Any:
        """Load ``contract.json`` next to an adapter (single source of method shapes)."""
        from ux_channel.bridge.bridge_contract import get_contract_registry, load_contract

        c = load_contract(path)
        get_contract_registry().add(c)
        # also mirror methods into plugin hub allowlist
        self.register(
            c.package,
            methods=c.method_names(),
            events=c.events,
            description=c.description,
            contract=c,
            npm=c.npm,
        )
        return c

    def contract(self, package: str) -> Any:
        """Return BridgeContract or None."""
        from ux_channel.bridge.bridge_contract import get_contract_registry

        return get_contract_registry().get(package)

    def describe(self, package: str) -> dict:
        """
        What Python knows about a package (from contract — not live npm introspection).

        True npm API discovery cannot cross into Python safely; the adapter contract
        is the dynamic surface you control.
        """
        c = self.contract(package)
        if c is None:
            return {
                "package": package,
                "known": False,
                "hint": "ch.bridge.load_contract('…/contract.json') or register(methods=…)",
                "lifecycle": ["mount", "update", "call", "destroy"],
            }
        return {"known": True, **c.as_dict()}

    def packages(self) -> list[str]:
        """Names of registered bridge manifests (npm package keys)."""
        try:
            from ux_channel.bridge.plugins import get_hub

            return sorted(get_hub().bridge_manifests.keys())
        except Exception:
            return []

    def diagnose(self) -> dict[str, Any]:
        return {
            "kind": "widget-bridge",
            "truth": "mount_spec Placement + mount_ops — no HTML in channel",
            "media": "use ch.media only (not ch.bridge)",
            "static": "ux-bridge.js",
            "packages": self.packages(),
            "contracts": __import__(
                "ux_channel.bridge.bridge_contract", fromlist=["get_contract_registry"]
            ).get_contract_registry().packages(),
            "npm_workspace": "packages/@ux-channel/*",
            "strategy_doc": "docs/NPM.md",
            "public_api": list(BRIDGE_PUBLIC_API),
            "docs": "docs/BRIDGE_STRATEGY.md",
        }


def attach_bridge(channel: Any) -> BridgePlane:
    plane = BridgePlane(channel)
    channel.bridge = plane
    return plane
