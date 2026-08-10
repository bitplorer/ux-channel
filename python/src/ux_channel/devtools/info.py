"""Package / runtime info for /version endpoints and diagnostics."""
from __future__ import annotations
from typing import Any, Optional, TYPE_CHECKING
from ux_channel._version import __version__
if TYPE_CHECKING:
    from ux_channel.host.registry import ActionRegistry

def package_info(registry: Optional["ActionRegistry"] = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "package": "ux-channel",
        "version": __version__,
        "protocol": "1",
        "v": "1",
    }
    if registry is not None:
        body["actions_count"] = len(registry.names())
        body["require_cap"] = bool(registry.require_cap)
        body["has_nonce_store"] = registry.nonce_store is not None
        body["has_idempotency_store"] = registry.idempotency_store is not None
    return body
