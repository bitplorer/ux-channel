"""Fake lab device-under-test adapter — flash once under QuantityBudget."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from ux_channel.foundations.io_channel import IoKind, IoMethodSpec, IoProtocol, IoRoomClaim
from ux_channel.foundations.quantity import Quantity


@dataclass
class LabDutAdapter:
    """
    Lab bench DUT:

    * COMMAND ``flash`` — budgeted (max 1 count); irreversible for demo
    * READING ``id`` — return dut id
    * STREAM methods are intentionally omitted (use WebRTC plane)
    """

    name: str = "lab.dut"
    dut_id: str = "dut-0"
    flash_count: int = 0
    log: list[str] = field(default_factory=list)

    def describe(self) -> IoProtocol:
        return IoProtocol(
            name=self.name,
            methods={
                "flash": IoMethodSpec(
                    "flash",
                    kind=IoKind.COMMAND,
                    scopes=frozenset({"lab", "lab.flash"}),
                    unit="count",
                    max_magnitude=1,
                    allow_event_keys=("dut_id",),
                    description="Flash firmware once per budgeted Quantity",
                ),
                "id": IoMethodSpec(
                    "id",
                    kind=IoKind.READING,
                    scopes=frozenset({"lab", "view"}),
                ),
            },
            events=frozenset({"ready"}),
        )

    def call(
        self,
        method: str,
        args: Sequence[Any],
        *,
        claim: IoRoomClaim,
        quantity: Optional[Quantity] = None,
    ) -> Any:
        if method == "id":
            return {"dut_id": self.dut_id, "flashes": self.flash_count}
        if method == "flash":
            self.flash_count += 1
            self.log.append(
                f"flash#{self.flash_count} peer={claim.peer_id} "
                f"q={quantity.magnitude if quantity else None}"
            )
            return {
                "ok": True,
                "dut_id": self.dut_id,
                "flash_count": self.flash_count,
                "peer": claim.peer_id,
            }
        raise ValueError(f"unknown lab method {method!r}")
