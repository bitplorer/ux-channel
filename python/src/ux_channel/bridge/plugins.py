"""Plugin system — plug-and-play integration points for ux-channel.
Uid Channel must stay **library-agnostic**: FastAPI, Starlette, Django, Jinja,
ux-dom, plain strings, and future stacks should all drive the same
Intent → Action → Result loop without forking the core.
This module defines *extension contracts* (protocols) and a small registry so
third-party packages can register:
  1.…"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from ux_channel.render.renderers import HtmlRenderer

logger = logging.getLogger("ux_channel.bridge.plugins")

# Entry-point group name for setuptools / importlib.metadata discovery.
ENTRY_POINT_GROUP = "ux_channel.bridge.plugins"


@runtime_checkable
class HostAdapter(Protocol):
    """
    Mount Channel HTTP routes onto a web application object.

    Designed so FastAPI, Starlette, Django, Litestar, etc. can each ship an
    adapter without the core importing them.

    Usage style::

        adapter = FastAPIHostAdapter()
        adapter.mount(app, registry, path=\"/ux-channel\")
    """

    name: str

    def mount(self, app: Any, registry: Any, *, path: str = "/ux-channel", **kwargs: Any) -> Any:
        """Attach action endpoint + static files; return whatever is natural for the host."""
        ...


@dataclass
class BridgeManifest:
    """
    Server-side description of an npm bridge package.

    Designed for **install-time / declare-time** mapping — not full reflection
    of arbitrary JS. The client ``ux-bridge.js`` loads an adapter registered
    under ``package``; this manifest documents the contract and helps Python
    emit correct host HTML + ops.

    Fields
    ------
    package:
        Key shared with ``data-channel-bridge-package`` and ``bridge.mount``.
    methods:
        Whitelist of callable method names (enforced in docs/client adapters).
    events:
        CustomEvent names the bridge host may emit toward HTMX/Channel triggers.
    js_module:
        Optional path/URL hint for bundlers (not loaded automatically in 0.1).
    version:
        Adapter version string for debugging.

    Usage::

        ChartJs = BridgeManifest(
            package=\"chart.js\",
            methods=(\"update\", \"destroy\", \"setActiveIndex\"),
            events=(\"uid:chart-select\",),
        )
        hub.add_bridge_manifest(ChartJs)
    """

    package: str
    methods: tuple[str, ...] = ()
    events: tuple[str, ...] = ()
    js_module: Optional[str] = None
    version: str = "1"
    description: str = ""

    def allows_method(self, method: str) -> bool:
        """True if method is whitelisted (empty whitelist = allow all — use carefully)."""
        if not self.methods:
            return True
        return method in self.methods


RegisterFn = Callable[["PluginHub"], None]


@dataclass
class PluginHub:
    """
    Central registry for plug-and-play extensions.

    Lifecycle
    ---------
    1. App creates ``ActionRegistry`` with a ``ChainRenderer``.
    2. App (or entry points) register renderers / manifests on the hub.
    3. Hub can build a ``ChainRenderer`` from registered renderers.
    4. Host adapter mounts HTTP using the same registry.

    Thread-safety: not required; register at startup only.
    """

    renderers: list[HtmlRenderer] = field(default_factory=list)
    host_adapters: dict[str, HostAdapter] = field(default_factory=dict)
    bridge_manifests: dict[str, BridgeManifest] = field(default_factory=dict)
    _entry_points_loaded: bool = False

    def add_renderer(self, renderer: HtmlRenderer, *, prepend: bool = False) -> None:
        """
        Register an HtmlRenderer.

        Order matters: first renderer that returns non-None wins in ChainRenderer.
        Use prepend=True for high-priority framework renderers (e.g. ux-dom).
        """
        if prepend:
            self.renderers.insert(0, renderer)
        else:
            self.renderers.append(renderer)

    def add_host_adapter(self, adapter: HostAdapter) -> None:
        """Register a web-framework host (e.g. name='fastapi')."""
        self.host_adapters[adapter.name] = adapter

    def add_bridge_manifest(self, manifest: BridgeManifest) -> None:
        """Declare an npm bridge contract for tooling + optional validation."""
        self.bridge_manifests[manifest.package] = manifest

    def get_bridge(self, package: str) -> Optional[BridgeManifest]:
        return self.bridge_manifests.get(package)

    def chain_renderer(self) -> HtmlRenderer:
        """
        Build a ChainRenderer: registered plugins first, then StringRenderer.

        Contributes: drop-in multi-library HTML encoding without ActionRegistry
        knowing about each library.
        """
        from ux_channel.render.renderers import ChainRenderer, StringRenderer

        # StringRenderer last — always available fallback for str fragments
        parts: list[HtmlRenderer] = list(self.renderers) + [StringRenderer()]
        return ChainRenderer(*parts)

    def mount(self, host: str, app: Any, registry: Any, **kwargs: Any) -> Any:
        """
        Plug-and-play mount: hub.mount('fastapi', app, reg).

        Raises KeyError if adapter not registered (call load_builtin_hosts()).
        """
        if host not in self.host_adapters:
            raise KeyError(
                f"no host adapter {host!r}; known: {sorted(self.host_adapters)} — "
                "call ux_channel.plugins.load_builtin_hosts(hub) or register your own"
            )
        return self.host_adapters[host].mount(app, registry, **kwargs)

    def load_entry_points(self) -> int:
        """
        Discover third-party plugins via importlib.metadata entry points.

        Returns number of plugins loaded. Failures are logged, not raised,
        so a broken optional plugin cannot take down the app.
        """
        if self._entry_points_loaded:
            return 0
        self._entry_points_loaded = True
        count = 0
        try:
            if sys.version_info >= (3, 10):
                from importlib.metadata import entry_points

                eps = entry_points()
                # Python 3.10+ SelectableGroups vs tuple
                group = eps.select(group=ENTRY_POINT_GROUP) if hasattr(eps, "select") else eps.get(ENTRY_POINT_GROUP, ())  # type: ignore[attr-defined,arg-type]
            else:  # pragma: no cover
                from importlib.metadata import entry_points

                group = entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover
            logger.warning("entry point discovery failed: %s", exc)
            return 0

        for ep in group:
            try:
                fn = ep.load()
                if callable(fn):
                    fn(self)
                    count += 1
                    logger.info("loaded ux_channel plugin: %s", ep.name)
            except Exception as exc:
                logger.exception("failed loading plugin %s: %s", getattr(ep, "name", ep), exc)
        return count

    def validate_bridge_call(self, package: str, method: str) -> None:
        """
        Optional server-side check before emitting bridge.call ops.

        Contributes: defense-in-depth so actions cannot invoke undeclared JS methods
        when a manifest is registered. Unknown packages are allowed (open by default).
        """
        m = self.bridge_manifests.get(package)
        if m is None:
            return
        if not m.allows_method(method):
            raise ValueError(
                f"method {method!r} not allowed for bridge package {package!r}; "
                f"allowed={m.methods}"
            )


# Process-wide default hub — apps may construct their own instead.
_default_hub: Optional[PluginHub] = None


def get_hub() -> PluginHub:
    """Return the process default PluginHub (created lazily)."""
    global _default_hub
    if _default_hub is None:
        _default_hub = PluginHub()
    return _default_hub


def set_hub(hub: PluginHub) -> None:
    """Replace the process default hub (tests / multi-app isolation)."""
    global _default_hub
    _default_hub = hub


def load_builtin_hosts(hub: Optional[PluginHub] = None) -> PluginHub:
    """
    Register built-in host adapters that are importable.

    Safe to call when FastAPI/Starlette are missing — skips unavailable hosts.
    Designed for::

        hub = load_builtin_hosts()
        reg = ActionRegistry(secret=..., renderer=hub.chain_renderer())
        hub.mount(\"fastapi\", app, reg)
    """
    hub = hub or get_hub()

    try:
        from ux_channel.asgi.fastapi import FastAPIHostAdapter

        hub.add_host_adapter(FastAPIHostAdapter())
    except ImportError:
        logger.debug("FastAPI host adapter not available")

    try:
        from ux_channel.asgi.starlette import StarletteHostAdapter

        hub.add_host_adapter(StarletteHostAdapter())
    except ImportError:
        logger.debug("Starlette host adapter not available")

    return hub


def load_builtin_renderers(hub: Optional[PluginHub] = None) -> PluginHub:
    """
    Register optional renderers when their libraries are installed.

    Order: ux-dom (if present) before Jinja — more specific object types first.
    StringRenderer is always added last by chain_renderer().
    """
    hub = hub or get_hub()

    try:
        from ux_channel.render.renderers import UxDomRenderer

        hub.add_renderer(UxDomRenderer(), prepend=True)
    except Exception:
        pass

    try:
        from ux_channel.render.renderers import JinjaRenderer

        # JinjaRenderer needs an environment — apps should register configured instance.
        # We only document the class; no bare registration without env.
        _ = JinjaRenderer
    except Exception:
        pass

    return hub
