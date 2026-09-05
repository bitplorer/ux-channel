"""Channel → frozen CEK noun encodings (cut #2).

This module must not import ``cek_host`` / ``cek_surface`` (off path stays
import-clean). Encodings are handshake / correlation only.

- ``flow_id`` → ``trace`` (LAW §10 / ADR 0007 — never authority)
- hello → Profile + Manifest (project ability bind; Manifest never grants Cap)
- stamp → handshake apply-set (not a Cap)

Frozen nouns are the CEK charter set. Do not invent a sixth product noun.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

# Charter nouns (cek-runtime / cek-framework). EffectGraph is Channel L7, not L1.
FROZEN_CEK_NOUNS = frozenset(
    {
        "Action",
        "BoundAsk",
        "Cap",
        "Context",
        "Intent",
        "Manifest",
        "Op",
        "Profile",
        "Receipt",
        "Result",
        "Trace",
    }
)

# Documented law generation id — do not import cek_host to read it.
LAW_GENERATION = "cek-law-1"

_BASELINE_APPLY = ("kv.set", "kv.delete", "log.append")
_UI_APPLY = ("ui.dom.morph", "ui.dom.restore")


def flow_id_to_trace(flow_id: Any) -> Optional[str]:
    """Map Channel ``flow_id`` to CEK ``trace``. Correlation only."""
    if flow_id is None:
        return None
    s = str(flow_id).strip()
    return s or None


def intent_trace(
    *,
    meta: Mapping[str, Any] | None = None,
    args: Mapping[str, Any] | None = None,
) -> Optional[str]:
    """Prefer explicit ``meta.trace``; else map ``flow_id`` → trace."""
    meta = meta or {}
    args = args or {}
    raw = meta.get("trace")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    return flow_id_to_trace(meta.get("flow_id") or args.get("flow_id"))


def hello_to_profile(hello: Mapping[str, Any] | None) -> dict[str, Any]:
    """Peer hello → CEK Profile (handshake / project ability). Not a Cap."""
    hello = hello or {}
    profiles = [str(p) for p in (hello.get("profiles") or []) if str(p).strip()]
    features = [str(f) for f in (hello.get("features") or []) if str(f).strip()]
    name = profiles[0] if profiles else "baseline"
    apply_set = [
        f
        for f in features
        if "." in f and f not in profiles and not f.startswith(("web.", "agent.", "trace.", "wire."))
    ]
    if not apply_set:
        apply_set = list(_BASELINE_APPLY)
        if "web.v1" in profiles or "ui" in features or "invoke" in features:
            apply_set.extend(_UI_APPLY)
    return {
        "name": name,
        "apply_set": apply_set,
        "unknown_op_policy": "skip",
    }


def hello_to_manifest(hello: Mapping[str, Any] | None) -> dict[str, Any]:
    """Peer hello → CEK Manifest (process handshake). Never grants Cap."""
    hello = hello or {}
    profiles = [str(p) for p in (hello.get("profiles") or []) if str(p).strip()]
    return {
        "law_generation": LAW_GENERATION,
        "accepted_generations": [LAW_GENERATION],
        "profiles": profiles,
        "fail_closed": {},
    }


def manifest_grants_cap(manifest: Mapping[str, Any] | None) -> bool:
    """Manifest is handshake only. Always False — never a Cap grant."""
    if not manifest:
        return False
    if any(k in manifest for k in ("cap", "token", "secret", "sig", "jti")):
        return False
    return False


def stamp_to_handshake(
    stamp_id: str,
    methods: Iterable[str] | None = None,
    *,
    kind: str = "invoke",
) -> dict[str, Any]:
    """Stamp table row → handshake encoding. Not a Cap (ADR 0001 / 0008)."""
    return {
        "stamp_id": str(stamp_id),
        "kind": str(kind or "invoke"),
        "methods": sorted({str(m) for m in (methods or []) if str(m).strip()}),
        "not_cap": True,
    }
