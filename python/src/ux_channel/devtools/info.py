"""Package / runtime info for /version endpoints and diagnostics."""
from __future__ import annotations
from typing import Any, Optional, TYPE_CHECKING
from ux_channel._version import __version__
if TYPE_CHECKING:
    from ux_channel.host.registry import ActionRegistry

def cmd_info(_: Any) -> int:
    from ux_channel import __version__
    from ux_channel.devtools.log import get_log

    log = get_log()
    log.section("info")
    info = package_info()
    print(f"ux-channel {__version__}")
    print("  PyPI / pip : ux-channel")
    print("  import     : ux_channel")
    print("  CLI        : uxchannel")
    for k, v in info.items():
        print(f"  {k}: {v}")
    log.ok("info complete", version=__version__)
    return 0


def cmd_check(args: Any) -> int:
    from ux_channel._version import __version__
    from ux_channel.devtools.log import get_log
    from ux_channel.host.config import ChannelConfig

    errors: list[str] = []
    env = (args.env or "production").lower()
    secret = args.secret or ""
    try:
        if env == "development":
            cfg = ChannelConfig.development(secret=secret or None)  # type: ignore[arg-type]
        else:
            if not secret:
                errors.append("production check requires --secret")
                cfg = None
            else:
                kwargs = {"allow_memory_stores": True} if args.allow_memory else {}
                cfg = ChannelConfig.production(secret, **kwargs)
    except ValueError as e:
        errors.append(str(e))
        cfg = None
    if cfg is not None and cfg.environment == "production" and not cfg.allow_memory_stores:
        import os

        if not (args.redis_url or os.environ.get("REDIS_URL")):
            errors.append("pass --allow-memory or set REDIS_URL")
    log = get_log()
    log.section("check")
    log.info(f"uxchannel check (library {__version__})")
    for err in errors:
        log.error(err)
    if errors:
        log.error("check FAIL")
        return 1
    log.ok("check OK")
    return 0


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
