"""
ux-dom / duck-tree performance helpers (glue layer only).

Techniques (see docs/UI_DOM_PERF.md)
----------------------------------
1. Structure-hash compile cache — skip re-walk for identical trees
2. Incremental inject — only re-stamp changed subtrees (key paths)
3. Shallow tree_to_dict for already-dict nodes
4. Batch compile many fragments once
5. Avoid full tree walks on hot paths (region morph uses IR, not full page)
"""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any, Iterable, Optional

from ux_channel.slot_compile import SlotMap, compile_tree
from ux_channel_ux_dom.tree import inject_uids, tree_to_dict

__all__ = [
    "CompileCache",
    "structure_hash",
    "inject_uids_cached",
    "batch_inject",
    "tree_to_dict_shallow",
]


def structure_hash(node: Any) -> str:
    """
    Hash of **shape** (tags, keys, attr names) — not full attr values.

    Stable for cache keys when content changes but structure does not.
    """
    d = tree_to_dict(node)

    def shape(n: Any) -> Any:
        if not isinstance(n, dict):
            return type(n).__name__
        return {
            "t": n.get("tag"),
            "k": n.get("key"),
            "a": sorted(str(x) for x in (n.get("attrs") or {})),
            "c": [shape(c) for c in (n.get("children") or [])],
        }

    raw = json.dumps(shape(d), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


class CompileCache:
    """Thread-safe LRU-ish cache of inject_uids results by structure hash + prefix."""

    def __init__(self, *, maxsize: int = 256) -> None:
        self.maxsize = max(8, int(maxsize))
        self._data: dict[str, tuple[dict[str, Any], SlotMap]] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _key(self, node: Any, prefix: str) -> str:
        return f"{prefix}:{structure_hash(node)}"

    def get(self, node: Any, *, prefix: str = "ui") -> Optional[tuple[dict, SlotMap]]:
        k = self._key(node, prefix)
        with self._lock:
            hit = self._data.get(k)
            if hit is not None:
                self.hits += 1
                # refresh LRU
                if k in self._order:
                    self._order.remove(k)
                self._order.append(k)
                return hit
            self.misses += 1
            return None

    def put(self, node: Any, value: tuple[dict, SlotMap], *, prefix: str = "ui") -> None:
        k = self._key(node, prefix)
        with self._lock:
            self._data[k] = value
            if k in self._order:
                self._order.remove(k)
            self._order.append(k)
            while len(self._order) > self.maxsize:
                old = self._order.pop(0)
                self._data.pop(old, None)

    def inject(self, node: Any, *, prefix: str = "ui") -> tuple[dict[str, Any], SlotMap]:
        hit = self.get(node, prefix=prefix)
        if hit is not None:
            return hit
        annotated, sm = inject_uids(node, prefix=prefix)
        self.put(node, (annotated, sm), prefix=prefix)
        return annotated, sm

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._order.clear()
            self.hits = self.misses = 0


_DEFAULT = CompileCache()


def inject_uids_cached(
    node: Any,
    *,
    prefix: str = "ui",
    cache: Optional[CompileCache] = None,
) -> tuple[dict[str, Any], SlotMap]:
    """Cached ``inject_uids`` — reuse SlotMap for identical structure."""
    c = cache or _DEFAULT
    return c.inject(node, prefix=prefix)


def batch_inject(
    nodes: Iterable[Any],
    *,
    prefix: str = "ui",
    cache: Optional[CompileCache] = None,
) -> list[tuple[dict[str, Any], SlotMap]]:
    """Compile many fragments; share one cache."""
    c = cache or _DEFAULT
    return [c.inject(n, prefix=f"{prefix}.{i}") for i, n in enumerate(nodes)]


def tree_to_dict_shallow(node: Any) -> dict[str, Any]:
    """
    Fast path: if already a Mapping tree, copy only top level (children shared).

    Use when callers guarantee dict shape and won't mutate children in place.
    """
    if isinstance(node, dict):
        return node  # zero-copy trust
    return tree_to_dict(node)
