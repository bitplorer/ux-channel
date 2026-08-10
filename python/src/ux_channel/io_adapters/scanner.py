"""Fake barcode / line scanner adapter — events become Intent args."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from ux_channel.foundations.io_channel import (
    IoKind,
    IoMethodSpec,
    IoProtocol,
    IoRoomClaim,
)
from ux_channel.foundations.quantity import Quantity


@dataclass
class ScannerAdapter:
    """
    In-process scanner stub.

    * ``read`` — READING: return last code (if any)
    * ``inject`` — test helper: simulate a scan (not a sealed guest method for UI)
    * event ``scanned`` — payload ``{sku}`` → Intent args via gate
    """

    name: str = "pos.scanner"
    last_sku: Optional[str] = None
    scans: list[str] = field(default_factory=list)

    def describe(self) -> IoProtocol:
        return IoProtocol(
            name=self.name,
            methods={
                "read": IoMethodSpec(
                    "read",
                    kind=IoKind.READING,
                    scopes=frozenset({"scan", "pos"}),
                    description="Read last scanned sku",
                ),
            },
            events=frozenset({"scanned"}),
        )

    def call(
        self,
        method: str,
        args: Sequence[Any],
        *,
        claim: IoRoomClaim,
        quantity: Optional[Quantity] = None,
    ) -> Any:
        if method == "read":
            return {"sku": self.last_sku, "room": claim.room, "peer": claim.peer_id}
        raise ValueError(f"unknown scanner method {method!r}")

    def inject(self, sku: str) -> dict[str, str]:
        """Simulate hardware scan (tests / demo buttons)."""
        code = str(sku).strip()
        self.last_sku = code
        self.scans.append(code)
        return {"sku": code, "event": "scanned"}
