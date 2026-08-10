"""
RegionDirectory — opt-in file/package discovery for Region workplaces.

Governing stance: shell feature. Core Intent plane works without this.
Enable via ChannelConfig.regions / ch.regions_dir.load(...).

::

    ch = Channel.boot(app, config=ChannelConfig.development(
        secret="...", regions="app.regions",
    ))
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Sequence, Type, Union

from ux_channel.host.region_component import Region, class_to_uid

__all__ = [
    "RegionDirectory",
    "path_to_uid",
    "attach_region_directory",
    "discover_region_classes",
]

log = logging.getLogger("ux_channel.regions_fs")


def path_to_uid(relative_posix: str) -> str:
    """pay/desk.py or pay/desk → pay.desk"""
    s = relative_posix.replace("\\", "/").strip("/")
    if s.endswith(".py"):
        s = s[:-3]
    if s.endswith("/__init__"):
        s = s[: -len("/__init__")]
    s = s.replace("/", ".")
    while ".." in s:
        s = s.replace("..", ".")
    return s.strip(".")


def _iter_modules(package_name: str) -> Iterator[tuple[str, str]]:
    """Yield (module_name, relative_path_under_package)."""
    pkg = importlib.import_module(package_name)
    if not hasattr(pkg, "__path__"):
        return
    prefix = package_name + "."
    for mod in pkgutil.walk_packages(pkg.__path__, prefix=prefix):
        if mod.ispkg:
            continue
        full = mod.name
        rel = full[len(prefix) :] if full.startswith(prefix) else full
        yield full, rel.replace(".", "/") + ".py"


def discover_region_classes(
    package: str,
) -> list[tuple[Type[Region], str, str]]:
    """
    Return list of (cls, uid, module_name).

    Skips classes with ``__region__ is False`` and abstract Region itself.
    """
    found: list[tuple[Type[Region], str, str]] = []
    seen: set[Type[Region]] = set()
    for mod_name, rel in _iter_modules(package):
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            log.warning("region discover import failed %s: %s", mod_name, exc)
            raise
        path_uid = path_to_uid(rel)
        for _n, obj in list(vars(mod).items()):
            if not inspect.isclass(obj):
                continue
            if obj is Region or not issubclass(obj, Region):
                continue
            if obj in seen:
                continue
            if getattr(obj, "__region__", True) is False:
                continue
            # only classes defined in this module (not imported re-exports)
            if getattr(obj, "__module__", None) != mod_name:
                continue
            seen.add(obj)
            uid = str(obj.uid) if getattr(obj, "uid", None) else path_uid
            # if class set uid=None explicitly, path wins via default_uid
            if not getattr(obj, "uid", None):
                # bind path default by setting on class only if unset
                uid = path_uid or obj.default_uid()
            found.append((obj, uid, mod_name))
    return found


class RegionDirectory:
    """
    In-memory map of uid → Region class / instance.

    Opt-in shell around Region.mount — does not replace hand mount.
    """

    def __init__(self, channel: Any) -> None:
        self.ch = channel
        self._classes: dict[str, Type[Region]] = {}
        self._instances: dict[str, Region] = {}
        self._modules: dict[str, str] = {}
        self._factories: dict[Type[Region], Callable[[Any], Region]] = {}

    def bind(self, cls: Type[Region], factory: Callable[[Any], Region]) -> None:
        """DI: how to construct a Region when loading/singleton."""
        self._factories[cls] = factory

    def load(
        self,
        package: str,
        *,
        mount_singletons: bool = True,
        strict: bool = True,
    ) -> "RegionDirectory":
        """Discover package and optionally mount singleton=True classes."""
        try:
            items = discover_region_classes(package)
        except Exception:
            if strict:
                raise
            log.exception("region load failed for %s", package)
            return self
        for cls, uid, mod_name in items:
            self._classes[uid] = cls
            self._modules[uid] = mod_name
            # Ensure class default uid matches discovery when not frozen on class
            if not cls.__dict__.get("uid"):
                # path-derived: store on directory only; instances use uid=
                pass
            if mount_singletons and getattr(cls, "singleton", False):
                self.mount(uid)
        return self

    def mount(self, uid: str, **scope: Any) -> Region:
        if uid in self._instances and self._instances[uid]._mounted:
            return self._instances[uid]
        cls = self._classes.get(uid)
        if cls is None:
            raise KeyError(f"unknown region uid {uid!r}")
        factory = self._factories.get(cls)
        if factory:
            inst = factory(self.ch)
            if not inst._mounted:
                inst.mount(self.ch)
        else:
            inst = cls(self.ch, uid=uid, **scope).mount()
        self._instances[uid] = inst
        return inst

    def get(self, uid: str) -> Optional[Region]:
        return self._instances.get(uid)

    def make(self, base_uid: str, key: str, **kw: Any) -> Region:
        cls = self._classes.get(base_uid)
        if cls is None:
            raise KeyError(f"unknown region base {base_uid!r}")
        return cls.make(self.ch, key, **kw)

    def uids(self) -> list[str]:
        return sorted(self._classes.keys())

    def list_dx(self) -> list[dict[str, Any]]:
        out = []
        for uid in self.uids():
            cls = self._classes[uid]
            actions = []
            for name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
                meta = getattr(member, "_ux_region_action", None)
                if meta:
                    wire = meta.get("name") or f"{uid}.{name}"
                    actions.append(wire)
            out.append(
                {
                    "uid": uid,
                    "class": cls.__name__,
                    "module": self._modules.get(uid),
                    "singleton": bool(getattr(cls, "singleton", False)),
                    "scopes": list(getattr(cls, "scopes", ()) or ()),
                    "actions": actions,
                    "mounted": uid in self._instances,
                }
            )
        return out


def attach_region_directory(channel: Any) -> RegionDirectory:
    existing = getattr(channel, "regions_dir", None)
    if isinstance(existing, RegionDirectory):
        return existing
    d = RegionDirectory(channel)
    channel.regions_dir = d
    # soft alias — do not clobber RegionBook on ch.regions
    if not hasattr(channel, "region_tree"):
        channel.region_tree = d
    return d


def boot_load_regions(channel: Any, config: Any = None) -> None:
    """Called from Channel.boot — no-op if regions not configured."""
    cfg = config or getattr(channel, "config", None)
    if cfg is None:
        return
    regions = getattr(cfg, "regions", None)
    auto = getattr(cfg, "regions_auto", True)
    if not regions and not auto:
        return
    packages: list[str] = []
    if regions is None:
        return  # opt-in: must set regions=
    if isinstance(regions, (list, tuple)):
        packages = [str(x) for x in regions]
    else:
        packages = [str(regions)]
    d = attach_region_directory(channel)
    strict = bool(getattr(cfg, "regions_strict", True))
    for pkg in packages:
        try:
            d.load(pkg, strict=strict)
        except ModuleNotFoundError:
            if strict:
                raise
            log.warning("regions package not found: %s", pkg)
