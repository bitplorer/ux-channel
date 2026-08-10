"""
Bridge API — npm widget hosts (not regions).

First principles
----------------
Some UI is better as a client library (Chart.js, Three.js, maps). A **bridge**
is a host DOM node + lifecycle ops:

1. SSR ``mount_html(id, package=..., props=...)``
2. Client ``ux-bridge.js`` mounts the package adapter
3. Server may ``bridge.update`` / ``bridge.call`` / ``bridge.destroy`` via Result ops

Bridges never replace **regions** for DB-backed HTML morphs. Regions morph
HTML; bridges talk to JS instances.

**There is no Python↔JS function binding.** Mapping is:
  Python emits op ``{op, id, package, method, args}`` (JSON)
  JS ``uxBridge`` looks up instance by ``id`` and runs ``method`` string
Stability = BridgeManifest methods + adapter contract + wire version — not import reflection.

Import from this module (not the ux_channel root)::

    from ux_channel.bridge.bridge_api import mount_html, mount_ops, update_ops

See: docs/PLUGINS.md, docs/ISLANDS.md (see bridges docs).
"""
from __future__ import annotations

from ux_channel.protocol import serde as _serde

import html
import json
from typing import Any, Mapping, Optional, Sequence

from ux_channel.protocol.ops import Op, bridge_call, bridge_destroy, bridge_mount, bridge_update
from ux_channel.bridge.plugins import BridgeManifest, get_hub


def props_attr(props: Any) -> str:
    """JSON-encode props for data-channel-bridge-props (HTML-escaped)."""
    raw = _serde.dumps(props, default=str)
    return html.escape(raw, quote=True)


def mount_html(
    bridge_id: str,
    *,
    package: str,
    props: Any = None,
    class_name: str = "",
    tag: str = "div",
    inner: str = "",
    include_props_attr: bool = True,
) -> str:
    """
    Render a host element for an npm bridge host.

    Designed so first paint can SSR the shell; client ux-bridge.js mounts on
    scan or after bridge.mount op.

    Parameters
    ----------
    bridge_id:
        Stable instance id (Result ops + data-channel-bridge-id).
    package:
        Adapter key (must match JS uxBridge.register and optional manifest).
    props:
        JSON-serializable props for initial mount.
    inner:
        Optional inner HTML (e.g. ``<canvas></canvas>`` for Chart.js).
    """
    cls = f' class="{html.escape(class_name, quote=True)}"' if class_name else ""
    props_s = ""
    if include_props_attr and props is not None:
        props_s = f' data-channel-bridge-props="{props_attr(props)}"'
    return (
        f'<{tag} data-channel-bridge-id="{html.escape(bridge_id, quote=True)}"'
        f' data-channel-bridge-package="{html.escape(package, quote=True)}"'
        f"{props_s}{cls}>{inner}</{tag}>"
    )


def mount_ops(
    bridge_id: str,
    package: str,
    *,
    props: Any = None,
    target: Optional[str] = None,
    hub: Any = None,
) -> list[Op]:
    """
    Ops to mount a bridge host after its host HTML is in the DOM.

    If a BridgeManifest is registered, package name is validated only for
    presence; methods are checked on call_ops.
    """
    hub = hub or get_hub()
    # Touch hub so apps that only use manifests still work
    _ = hub.get_bridge(package)
    return [
        bridge_mount(
            bridge_id,
            package,
            props=props,
            target=target or f'[data-channel-bridge-id="{bridge_id}"]',
        )
    ]


def update_ops(
    bridge_id: str,
    props: Any,
    *,
    replace: bool = False,
) -> list[Op]:
    """Ops to push new props without remounting (adapter.update)."""
    return [bridge_update(bridge_id, props, replace=replace)]


def call_ops(
    bridge_id: str,
    method: str,
    *args: Any,
    package: Optional[str] = None,
    hub: Any = None,
) -> list[Op]:
    """
    Ops to call a whitelisted instance method.

    If ``package`` is provided and a manifest exists, method is validated.
    """
    hub = hub or get_hub()
    if package:
        hub.validate_bridge_call(package, method)
    return [
        bridge_call(
            bridge_id,
            method,
            list(args),
            package=package,
        )
    ]


def destroy_ops(bridge_id: str) -> list[Op]:
    """Ops to tear down a bridge host instance."""
    return [bridge_destroy(bridge_id)]


def register_simple_manifest(
    package: str,
    *,
    methods: Sequence[str] = (),
    events: Sequence[str] = (),
    description: str = "",
    hub: Any = None,
) -> BridgeManifest:
    """
    Convenience: declare a bridge package for plug-and-play tooling.

    Usage at app startup::

        register_simple_manifest(\"chart.js\", methods=[\"update\", \"destroy\"])
    """
    hub = hub or get_hub()
    m = BridgeManifest(
        package=package,
        methods=tuple(methods),
        events=tuple(events),
        description=description,
    )
    hub.add_bridge_manifest(m)
    return m
