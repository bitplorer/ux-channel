"""
Placement — framework-agnostic **data** (one source of truth).

uxchannel does **not** own documents. It emits:

* ``attrs`` — dict of data-* / protocol attributes
* ``client`` — JSON-serializable opts for JS join/boot
* ``scripts`` — ordered script *references* (URLs), not ``<script>`` strings

ux-dom / Jinja / React turn Placement into markup. Demo HTML helpers live in
``ux_channel.render.kit`` only.
"""

from __future__ import annotations

def _serde():
    from ux_channel.protocol import serde as _m
    return _m



import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

__all__ = ["ScriptRef", "Placement", "scripts_to_urls"]


@dataclass(frozen=True)
class ScriptRef:
    """One client script to load (path or absolute URL)."""

    src: str
    defer: bool = True
    module: bool = False
    # optional id for dedupe
    id: str = ""

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"src": self.src}
        if self.defer:
            d["defer"] = True
        if self.module:
            d["type"] = "module"
        if self.id:
            d["id"] = self.id
        return d


@dataclass(frozen=True)
class Placement:
    """
    Single placement bag — **no HTML fields**.

    ::

        p = ch.media.plugin(room, sub=user)
        # ux-dom:
        #   for s in p.scripts: Script(src=s.src, defer=s.defer)
        #   **p.attrs  or Element(**attrs_py)
        #   data-client = p.client_json
    """

    attrs: Mapping[str, str] = field(default_factory=dict)
    client: Mapping[str, Any] = field(default_factory=dict)
    scripts: tuple[ScriptRef, ...] = ()
    path: str = ""
    kind: str = ""  # "media" | "runtime" | "bridge-mount" | …
    meta: Mapping[str, Any] = field(default_factory=dict)

    @property
    def client_json(self) -> str:
        return _serde().dumps(dict(self.client), default=str)

    @property
    def attrs_py(self) -> dict[str, str]:
        """Underscore keys for Python HTML DSLs that map ``_`` → ``-``."""
        return {k.replace("-", "_"): v for k, v in self.attrs.items()}

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "attrs": dict(self.attrs),
            "attrs_py": self.attrs_py,
            "client": dict(self.client),
            "client_json": self.client_json,
            "scripts": [s.as_dict() for s in self.scripts],
            "meta": dict(self.meta),
        }

    def merge_scripts(self, *extra: ScriptRef | Iterable[ScriptRef]) -> "Placement":
        bag: list[ScriptRef] = list(self.scripts)
        for item in extra:
            if isinstance(item, ScriptRef):
                bag.append(item)
            else:
                bag.extend(item)
        # dedupe by src preserving order
        seen: set[str] = set()
        out: list[ScriptRef] = []
        for s in bag:
            if s.src in seen:
                continue
            seen.add(s.src)
            out.append(s)
        return Placement(
            attrs=dict(self.attrs),
            client=dict(self.client),
            scripts=tuple(out),
            path=self.path,
            kind=self.kind,
            meta=dict(self.meta),
        )


def scripts_to_urls(scripts: Sequence[ScriptRef]) -> list[str]:
    return [s.src for s in scripts]
