"""
Lottie animation bridge — stunning motion from JSON/CDN.

    motion = LottieBridge(ch)
    hero = motion("hero", src="https://…/success.json", loop=True)
    return hero.play()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["LottieBridge", "LOTTIE_PACKAGE"]

LOTTIE_PACKAGE = "lottie-web"
LOTTIE_METHODS = ("update", "destroy", "play", "pause", "stop", "setSpeed", "goToAndPlay")


@dataclass
class _State:
    src: str = ""
    animation_data: dict | None = None
    loop: bool = True
    autoplay: bool = True
    speed: float = 1.0
    renderer: str = "svg"  # svg | canvas
    background: str = "transparent"


class LottieBridge(BridgeFactoryMixin):
    package = LOTTIE_PACKAGE
    methods = LOTTIE_METHODS
    description = "Lottie-web animations"

    def __init__(
        self,
        ch: Any,
        id: str | None = None,
        *,
        src: str = "",
        animation_data: dict | None = None,
        loop: bool = True,
        autoplay: bool = True,
        speed: float = 1.0,
        renderer: str = "svg",
        background: str = "transparent",
        auto_register: bool = True,
    ) -> None:
        super().__init__(
            ch,
            id,
            src=src,
            animation_data=animation_data,
            loop=loop,
            autoplay=autoplay,
            speed=speed,
            renderer=renderer,
            background=background,
            auto_register=auto_register,
        )

    def _new_state(self, **kwargs: Any) -> _State:
        return _State(**{k: v for k, v in kwargs.items() if k in _State.__dataclass_fields__})

    def _build_props(self) -> dict[str, Any]:
        st = self._state
        props: dict[str, Any] = {
            "loop": bool(st.loop),
            "autoplay": bool(st.autoplay),
            "speed": float(st.speed),
            "renderer": st.renderer,
            "background": st.background,
        }
        if st.src:
            props["src"] = st.src
        if st.animation_data is not None:
            props["animationData"] = st.animation_data
        return props

    def play(self) -> Any:
        return self.fire("play")

    def pause(self) -> Any:
        return self.fire("pause")

    def stop(self) -> Any:
        return self.fire("stop")

    def set_speed(self, speed: float) -> Any:
        self.configure(speed=speed)
        return self.fire("setSpeed", float(speed))
