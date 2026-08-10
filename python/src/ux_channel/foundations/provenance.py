"""Provenance — durable source stamps for sensitive values.

* Used by ``Quantity.from_store`` (preferred) to build stamps from
  ``source`` / ``revision`` / ``principal``.
* Client/session bags must not mint provenance.

Fields: ``source`` (locator), ``revision`` (edition of that source),
optional ``principal`` (who loaded)."""


from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar, Union

__all__ = [
    "Provenance",
    "Provenanced",
    "ProvenanceError",
    "stamp",
    "require_provenance",
    "unwrap",
]

T = TypeVar("T")


class ProvenanceError(ValueError):
    """Missing or invalid provenance for a sensitive value."""


@dataclass(frozen=True)
class Provenance:
    """Where a value came from (durable truth)."""

    source: str  # e.g. db.order.42.amount
    revision: Union[str, int] = 0
    principal: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "revision": self.revision,
            "principal": self.principal,
        }


@dataclass(frozen=True)
class Provenanced(Generic[T]):
    value: T
    provenance: Provenance

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "provenance": self.provenance.to_dict()}


def stamp(
    value: T,
    source: str,
    *,
    revision: Union[str, int] = 0,
    principal: Optional[str] = None,
) -> Provenanced[T]:
    return Provenanced(value, Provenance(source=source, revision=revision, principal=principal))


def require_provenance(obj: Any, *, what: str = "value") -> Provenanced[Any]:
    if isinstance(obj, Provenanced):
        if not obj.provenance.source:
            raise ProvenanceError(f"{what}: empty provenance source")
        return obj
    raise ProvenanceError(
        f"{what}: missing provenance — load from durable store and stamp()"
    )


def unwrap(obj: Any, *, require: bool = True) -> Any:
    if isinstance(obj, Provenanced):
        return obj.value
    if require:
        raise ProvenanceError("unwrap requires Provenanced")
    return obj
