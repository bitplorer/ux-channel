"""Cap attenuation — child capabilities may only narrow parent authority.

* Law: scopes/caveats of a child ⊆ parent; never widen.
* Pairs with ``tree_cap`` (document-shaped envelopes) and ``CapService``."""


from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from ux_channel.protocol.capability import CapError, CapService

__all__ = ["AttenuationError", "CapEnvelope", "attenuate", "verify_attenuated"]


class AttenuationError(CapError):
    """Child cap would widen parent authority."""


@dataclass(frozen=True)
class CapEnvelope:
    """
    Structured view of a capability after verify.

    ``caveats`` are required scopes the holder must not exceed.
    ``parent_fp`` binds this token to a parent cap fingerprint (optional root).
    """

    token: str
    action: str
    args_hash: str
    caveats: tuple[str, ...] = ()
    parent_fp: Optional[str] = None
    sub: Optional[str] = None
    raw: Mapping[str, Any] = field(default_factory=dict)


def fingerprint_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]


def _caveat_set(scopes: Optional[Sequence[str]]) -> set[str]:
    return {str(s) for s in (scopes or ()) if s}


def attenuate(
    caps: CapService,
    action: str,
    args: Optional[Mapping[str, Any]] = None,
    *,
    parent_token: Optional[str] = None,
    caveats: Optional[Sequence[str]] = None,
    sub: Optional[str] = None,
    once: bool = False,
    extra: Optional[Mapping[str, Any]] = None,
) -> str:
    """
    Mint a cap that is **at most as powerful** as ``parent_token``.

    * Root (no parent): caveats become the scope set.
    * Child: caveats must be ⊆ parent scopes (or parent has ``*``).
    * ``parent_fp`` sealed into extra so verify can bind the chain.
    """
    cave = list(caveats or [])
    parent_fp = None
    parent_scopes: Optional[set[str]] = None

    if parent_token:
        parent = caps.verify(
            parent_token, action, args or {}, expected_sub=sub, consume_once=False
        )
        # Parent may be for a broader action only if action matches —
        # attenuation is same-action by default (safe). Cross-action needs explicit allow.
        parent_scopes = _caveat_set(parent.get("scopes"))
        if parent_scopes and "*" not in parent_scopes:
            child = _caveat_set(cave)
            if not child:
                # inherit parent scopes when child omits
                cave = sorted(parent_scopes)
            elif not child.issubset(parent_scopes):
                raise AttenuationError(
                    f"caveats {sorted(child - parent_scopes)} not allowed by parent"
                )
        parent_fp = fingerprint_token(parent_token)
        # also bind parent args: child args must match parent hash for sealed trust
        # (already enforced by verify with same args)

    extra_out = dict(extra or {})
    if parent_fp:
        extra_out["parent_fp"] = parent_fp
    if cave:
        extra_out["caveats"] = list(cave)

    return caps.mint(
        action,
        args,
        extra=extra_out or None,
        sub=sub,
        scopes=cave or None,
        once=once,
    )


def verify_attenuated(
    caps: CapService,
    token: str,
    action: str,
    args: Optional[Mapping[str, Any]] = None,
    *,
    parent_token: Optional[str] = None,
    required_caveats: Optional[Sequence[str]] = None,
    expected_sub: Optional[str] = None,
) -> CapEnvelope:
    """Verify cap and optional parent linkage + required caveats."""
    data = caps.verify(
        token,
        action,
        args,
        expected_sub=expected_sub,
        required_scopes=required_caveats,
        consume_once=False,
    )
    parent_fp = (data.get("extra") or {}).get("parent_fp")
    if parent_token is not None:
        expect = fingerprint_token(parent_token)
        if parent_fp != expect:
            raise AttenuationError("capability parent fingerprint mismatch")
        # ensure parent still valid for same action/args
        caps.verify(
            parent_token, action, args, expected_sub=expected_sub, consume_once=False
        )

    caveats = tuple(data.get("scopes") or (data.get("extra") or {}).get("caveats") or ())
    return CapEnvelope(
        token=token,
        action=str(data.get("action")),
        args_hash=str(data.get("args_hash")),
        caveats=caveats,
        parent_fp=parent_fp,
        sub=data.get("sub"),
        raw=data,
    )
