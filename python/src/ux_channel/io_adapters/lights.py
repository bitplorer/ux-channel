"""Fake home/party lights adapter — scope-limited commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from ux_channel.foundations.io_channel import IoKind, IoMethodSpec, IoProtocol, IoRoomClaim
from ux_channel.foundations.quantity import Quantity


@dataclass
class LightsAdapter:
    """
    Party-mode lights: only ``lights`` scope methods.

    COMMAND ``set`` args: (on: bool) or ({"on": bool})
    COMMAND ``scene`` args: (name: str) — allowlisted scenes only
    """

    name: str = "home.lights"
    on: bool = False
    scene: str = "off"
    allowed_scenes: frozenset[str] = field(
        default_factory=lambda: frozenset({"party", "dim", "off", "focus"})
    )
    history: list[str] = field(default_factory=list)

    def describe(self) -> IoProtocol:
        return IoProtocol(
            name=self.name,
            methods={
                "set": IoMethodSpec(
                    "set",
                    kind=IoKind.COMMAND,
                    scopes=frozenset({"lights"}),
                    description="Turn lights on/off",
                ),
                "scene": IoMethodSpec(
                    "scene",
                    kind=IoKind.COMMAND,
                    scopes=frozenset({"lights"}),
                    description="Apply allowlisted scene",
                ),
                "status": IoMethodSpec(
                    "status",
                    kind=IoKind.READING,
                    scopes=frozenset({"lights", "view"}),
                ),
            },
            events=frozenset(),
        )

    def call(
        self,
        method: str,
        args: Sequence[Any],
        *,
        claim: IoRoomClaim,
        quantity: Optional[Quantity] = None,
    ) -> Any:
        if method == "status":
            return {"on": self.on, "scene": self.scene, "room": claim.room}
        if method == "set":
            on = bool(args[0]) if args else False
            if args and isinstance(args[0], dict):
                on = bool(args[0].get("on", False))
            self.on = on
            self.history.append(f"set:{on}")
            return {"on": self.on}
        if method == "scene":
            name = str(args[0]) if args else "off"
            if name not in self.allowed_scenes:
                raise ValueError(f"scene {name!r} not allowlisted")
            self.scene = name
            self.on = name != "off"
            self.history.append(f"scene:{name}")
            return {"scene": self.scene, "on": self.on}
        raise ValueError(f"unknown lights method {method!r}")
