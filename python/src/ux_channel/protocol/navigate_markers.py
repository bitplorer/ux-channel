"""Handler return markers for full navigation (no renderer dependency)."""

from __future__ import annotations


class Navigate:
    """Special return: full navigation."""

    def __init__(self, href: str, *, replace: bool = False):
        self.href = href
        self.replace = replace


class Go(Navigate):
    """Alias for Navigate (shorter DX)."""
