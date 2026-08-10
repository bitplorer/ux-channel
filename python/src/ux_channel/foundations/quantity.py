"""
Quantity — store-grounded measure (magnitude + unit + provenance).

Power public::

    from ux_channel.foundations.quantity import Quantity
    Quantity.from_store(magnitude, unit, *, source, revision=0, principal=None)

Builds ``Provenance`` internally. Prefer this over hand-building provenance.
Session/client may hold **references** (order_id, sku) — never bare quantities.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional, Union

from ux_channel.foundations.provenance import Provenance

__all__ = [
    "Quantity",
    "QuantityError",
    "QuantityBudget",
    "as_quantity",
    "refuse_client_quantity",
    "refuse_session_quantity",
    "path_looks_like_quantity",
]


class QuantityError(ValueError):
    """Illegal quantity placement or missing provenance."""


Number = Union[int, float, str, Decimal]


@dataclass(frozen=True)
class Quantity:
    """
    Store-grounded measure — always provenanced.

    ``magnitude`` + ``unit`` are sector-neutral (USD, kg, seats, mg, credits, …).
    Construct via ``Quantity.from_store`` (preferred).
    """

    magnitude: Decimal
    unit: str
    provenance: Provenance

    @classmethod
    def from_store(
        cls,
        magnitude: Number,
        unit: str,
        *,
        source: str,
        revision: Union[str, int] = 0,
        principal: Optional[str] = None,
    ) -> "Quantity":
        """Load from durable store and stamp provenance (any sector)."""
        return cls(
            magnitude=Decimal(str(magnitude)),
            unit=str(unit).strip(),
            provenance=Provenance(
                source=source, revision=revision, principal=principal
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "magnitude": str(self.magnitude),
            "unit": self.unit,
            "provenance": self.provenance.to_dict(),
        }

    def __float__(self) -> float:
        return float(self.magnitude)

    def __str__(self) -> str:
        return f"{self.magnitude} {self.unit}".strip()


@dataclass(frozen=True)
class QuantityBudget:
    """Caveat for a cap / envelope — max magnitude in a unit."""

    max_magnitude: Optional[Decimal] = None
    unit: str = ""

    def allows(self, quantity: Quantity) -> bool:
        if self.unit and str(self.unit).strip():
            if quantity.unit.strip().lower() != str(self.unit).strip().lower():
                return False
        if self.max_magnitude is None:
            return True
        return Decimal(str(quantity.magnitude)) <= Decimal(str(self.max_magnitude))


def as_quantity(value: Any) -> Optional[Quantity]:
    """Coerce Quantity or dict payload; else None."""
    if isinstance(value, Quantity):
        return value
    if isinstance(value, dict) and "magnitude" in value and "unit" in value:
        prov = value.get("provenance") or {}
        if not isinstance(prov, dict) or not prov.get("source"):
            return None
        return Quantity(
            magnitude=Decimal(str(value["magnitude"])),
            unit=str(value["unit"]),
            provenance=Provenance(
                source=str(prov["source"]),
                revision=prov.get("revision", 0),
                principal=prov.get("principal"),
            ),
        )
    return None


def path_looks_like_quantity(path: str) -> bool:
    """True when a state/client path looks like durable measure authority."""
    from ux_channel.host.state_planes import path_is_risky

    return path_is_risky(path)


def refuse_session_quantity(key: str, value: Any) -> None:
    """Session chrome must not hold bare numeric quantity authority."""
    if value is None:
        return
    if isinstance(value, Quantity):
        raise QuantityError(
            f"session key {key!r} must not store Quantity — keep ids, load from store"
        )
    if not path_looks_like_quantity(key):
        return
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float, Decimal)):
        raise QuantityError(
            f"session key {key!r} looks like quantity authority — "
            "store only references (order_id, sku); load Quantity from durable store"
        )
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return
        try:
            Decimal(s)
        except Exception:
            return
        raise QuantityError(
            f"session key {key!r} looks like quantity authority — refuse numeric string"
        )


def refuse_client_quantity(path: str, value: Any = None) -> None:
    """Client plane must not accept quantity-like paths (or Quantity values)."""
    if isinstance(value, Quantity):
        raise QuantityError(
            f"client path {path!r} must not carry Quantity — use durable store"
        )
    if path_looks_like_quantity(path):
        raise QuantityError(
            f"client path {path!r} looks like durable quantity — refuse"
        )
