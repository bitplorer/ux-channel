
"""Swiper carousel bridge — galleries and marketing carousels."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Sequence
from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["SwiperBridge", "SWIPER_PACKAGE"]
SWIPER_PACKAGE = "swiper"
SWIPER_METHODS = ("update", "destroy", "slideTo", "slideNext", "slidePrev")

@dataclass
class _State:
    slides: list = field(default_factory=list)  # strings (html/text) or {html, title}
    loop: bool = True
    autoplay_ms: int = 0
    pagination: bool = True
    navigation: bool = True
    space_between: int = 16
    slides_per_view: float | int | str = 1

class SwiperBridge(BridgeFactoryMixin):
    package = SWIPER_PACKAGE
    methods = SWIPER_METHODS
    description = "Swiper carousel"

    def __init__(self, ch, id=None, *, slides=None, loop=True, autoplay_ms=0,
                 pagination=True, navigation=True, space_between=16,
                 slides_per_view=1, auto_register=True):
        super().__init__(
            ch, id, slides=list(slides or []), loop=loop, autoplay_ms=autoplay_ms,
            pagination=pagination, navigation=navigation, space_between=space_between,
            slides_per_view=slides_per_view, auto_register=auto_register,
        )

    def _new_state(self, **kw):
        return _State(**{k: v for k, v in kw.items() if k in _State.__dataclass_fields__})

    def _build_props(self):
        st = self._state
        slides = []
        for s in st.slides:
            if isinstance(s, dict):
                slides.append({"html": s.get("html", s.get("content", "")), "title": s.get("title", "")})
            else:
                slides.append({"html": str(s)})
        return {
            "slides": slides,
            "loop": bool(st.loop),
            "autoplayMs": int(st.autoplay_ms),
            "pagination": bool(st.pagination),
            "navigation": bool(st.navigation),
            "spaceBetween": int(st.space_between),
            "slidesPerView": st.slides_per_view,
        }

    def slide_to(self, index: int):
        return self.fire("slideTo", int(index))
