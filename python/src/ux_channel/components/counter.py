"""Counter — drop-in ± / reset widget."""

from __future__ import annotations

from typing import Any

from ux_channel.components.base import ChannelComponent
from ux_channel.protocol.types import Result


class Counter(ChannelComponent):
    """
    Stateful counter with inc / dec / reset.

    ::

        c = Counter(ch, uid="Cart:qty", min_value=0, max_value=99).install()
        html = c.render(n=1)
        # actions: Cart:qty uses name → default Counter.inc if name=Counter
    """

    kind = "Counter"

    def __init__(
        self,
        channel,
        *,
        uid: str | None = None,
        name: str = "Counter",
        min_value: int | None = None,
        max_value: int | None = None,
        step: int = 1,
        show_reset: bool = True,
    ):
        super().__init__(channel, uid=uid, name=name)
        self.min_value = min_value
        self.max_value = max_value
        self.step = step
        self.show_reset = show_reset

    def _clamp(self, n: int) -> int:
        if self.min_value is not None:
            n = max(self.min_value, n)
        if self.max_value is not None:
            n = min(self.max_value, n)
        return n

    def render(self, **state: Any) -> str:
        n = int(state.get("n", 0))
        n = self._clamp(n)
        parts = [
            self.btn("−", "dec", trust={"n": n}, class_name="ux-c-btn"),
            f'<span class="ux-c-val" style="min-width:2rem;text-align:center;display:inline-block">{n}</span>',
            self.btn("+", "inc", trust={"n": n}, class_name="ux-c-btn"),
        ]
        if self.show_reset:
            parts.append(self.btn("Reset", "reset", trust={}, class_name="ux-c-btn ux-c-reset"))
        inner = " ".join(parts)
        return self.wrap(
            inner,
            class_="ux-counter",
            style="display:flex;gap:.5rem;align-items:center;font:system-ui",
        )

    def _register(self) -> None:
        step = self.step
        comp = self

        @self.ch.action(self.action_name("inc"))
        def inc(n: int = 0) -> Result:
            return comp.refresh(n=comp._clamp(n + step))

        @self.ch.action(self.action_name("dec"))
        def dec(n: int = 0) -> Result:
            return comp.refresh(n=comp._clamp(n - step))

        @self.ch.action(self.action_name("reset"))
        def reset() -> Result:
            base = comp.min_value if comp.min_value is not None else 0
            return comp.refresh(n=base, notice="Reset")
