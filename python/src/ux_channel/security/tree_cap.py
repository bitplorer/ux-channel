"""Capability-shaped documents — envelopes attenuate down the tree.

* Pure channel dict trees; ux-dom conversion lives in ``ux_channel_ux_dom``.
* Trust maps hold **ids only** — not Quantity magnitudes."""


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

from ux_channel.protocol.capability import CapService
from ux_channel.security.attenuate import AttenuationError, attenuate, fingerprint_token

__all__ = [
    "TreeCapError",
    "TreeEnvelope",
    "nest_envelope",
    "validate_control",
    "compile_tree_caps",
]


class TreeCapError(AttenuationError):
    """Control or trust field not allowed under current tree envelope."""


@dataclass(frozen=True)
class TreeEnvelope:
    """
    Capability envelope at a node in the document tree.

    ``scopes`` — what actions/domains are allowed under this node.
    ``trust`` — sealed key→value the node may pass to controls (ids only).
    ``max_money`` — optional upper bound for money-related actions (display units).
    ``once`` — child controls may require once caps.
    ``parent_fp`` — fingerprint of parent cap token (optional).
    """

    scopes: frozenset[str] = field(default_factory=frozenset)
    trust: Mapping[str, Any] = field(default_factory=dict)
    max_money: Optional[float] = None
    once: bool = False
    parent_token: Optional[str] = None
    path: str = "root"

    def allows_scope(self, scope: str) -> bool:
        if not self.scopes or "*" in self.scopes:
            return True
        if scope in self.scopes:
            return True
        # prefix: pay allows pay.execute
        return any(scope.startswith(s + ".") or s.startswith(scope + ".") for s in self.scopes)

    def allows_trust(self, key: str, value: Any) -> bool:
        if key not in self.trust:
            # new trust keys cannot appear below root without grant
            return False
        return self.trust[key] == value


def nest_envelope(
    parent: TreeEnvelope,
    *,
    scopes: Optional[Sequence[str]] = None,
    trust: Optional[Mapping[str, Any]] = None,
    max_money: Optional[float] = None,
    once: Optional[bool] = None,
    path: str = "",
) -> TreeEnvelope:
    """Child envelope ⊆ parent (never wider)."""
    child_scopes = frozenset(scopes) if scopes is not None else parent.scopes
    if parent.scopes and "*" not in parent.scopes:
        if child_scopes and "*" in child_scopes:
            raise TreeCapError("child cannot introduce * under limited parent")
        if child_scopes and not child_scopes.issubset(parent.scopes):
            # allow nested scope pay.execute under parent pay
            for s in child_scopes:
                if s not in parent.scopes and not any(
                    s.startswith(p + ".") for p in parent.scopes
                ):
                    raise TreeCapError(f"scope {s!r} not allowed under parent {sorted(parent.scopes)}")

    parent_trust = dict(parent.trust)
    child_trust = dict(trust) if trust is not None else dict(parent_trust)
    for k, v in child_trust.items():
        if k in parent_trust and parent_trust[k] != v:
            raise TreeCapError(f"trust {k!r} conflicts with parent")
        if k not in parent_trust and parent_trust:
            # cannot invent new trust ids under a locked parent
            raise TreeCapError(f"trust key {k!r} not granted by parent")

    money = parent.max_money if max_money is None else max_money
    if parent.max_money is not None and money is not None and money > parent.max_money:
        raise TreeCapError("max_money cannot exceed parent")

    return TreeEnvelope(
        scopes=child_scopes if child_scopes else parent.scopes,
        trust=child_trust,
        max_money=money,
        once=parent.once if once is None else bool(once) or parent.once,
        parent_token=parent.parent_token,
        path=path or parent.path,
    )


def validate_control(
    env: TreeEnvelope,
    *,
    action: str,
    trust: Optional[Mapping[str, Any]] = None,
    scope: Optional[str] = None,
) -> None:
    """Reject controls the envelope does not authorize."""
    sc = scope or action
    if not env.allows_scope(sc) and not env.allows_scope(action):
        raise TreeCapError(f"action {action!r} not in envelope scopes at {env.path}")
    for k, v in dict(trust or {}).items():
        if env.trust and not env.allows_trust(k, v):
            raise TreeCapError(
                f"trust {k}={v!r} not allowed under envelope at {env.path}"
            )


def compile_tree_caps(
    tree: Mapping[str, Any],
    root: TreeEnvelope,
    *,
    caps: Optional[CapService] = None,
    action_attr: str = "data-channel-action",
) -> tuple[dict[str, Any], list[str]]:
    """
    Walk tree dict; validate embedded controls; return (tree, errors).

    Recognizes control attrs:
      * data-channel-action / data_channel_action
      * data-channel-trust-* or trust dict on node
      * node["control"] = {action, trust, scope}
    """
    errors: list[str] = []
    out = _walk(tree, root, errors=errors, caps=caps, action_attr=action_attr, path="root")
    return out, errors


def _walk(
    node: Any,
    env: TreeEnvelope,
    *,
    errors: list[str],
    caps: Optional[CapService],
    action_attr: str,
    path: str,
) -> Any:
    if not isinstance(node, Mapping):
        return node
    # optional per-node envelope narrow
    node_env = env
    if "envelope" in node:
        e = node["envelope"]
        try:
            node_env = nest_envelope(
                env,
                scopes=e.get("scopes"),
                trust=e.get("trust"),
                max_money=e.get("max_money"),
                once=e.get("once"),
                path=path,
            )
        except TreeCapError as exc:
            errors.append(f"{path}: {exc}")
            node_env = env

    ctrl = node.get("control")
    attrs = dict(node.get("attrs") or {})
    action = None
    trust: dict[str, Any] = {}
    if isinstance(ctrl, Mapping):
        action = ctrl.get("action")
        trust = dict(ctrl.get("trust") or {})
    else:
        action = attrs.get(action_attr) or attrs.get(action_attr.replace("-", "_"))
        for k, v in list(attrs.items()):
            kk = k.replace("-", "_")
            if kk.startswith("data_channel_trust_") or kk.startswith("trust_"):
                key = kk.split("trust_")[-1]
                trust[key] = v

    if action:
        try:
            validate_control(node_env, action=str(action), trust=trust)
        except TreeCapError as exc:
            errors.append(f"{path}: {exc}")

    kids_in = node.get("children") or []
    kids_out = []
    tag = node.get("tag") or "node"
    key = node.get("key")
    for i, ch in enumerate(kids_in):
        cp = f"{path}/{key if key is not None else tag}:{i}"
        kids_out.append(
            _walk(ch, node_env, errors=errors, caps=caps, action_attr=action_attr, path=cp)
        )
    out = dict(node)
    out["attrs"] = attrs
    out["children"] = kids_out
    out["_envelope_path"] = path
    return out
