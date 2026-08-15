"""
High-level factory — production and development bootstrap.

If REDIS_URL is set (or redis_url=), auto-wires Redis nonce / idempotency / push
and a Redis rate-limit before-hook (requires redis package).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from ux_channel.bridge.plugins import PluginHub

from ux_channel.host.registry import ActionRegistry


def _maybe_redis_stores(redis_url: str | None):
    if not redis_url:
        return None, None, None
    try:
        from ux_channel.redis_extra import (
            RedisIdempotencyStore,
            RedisNonceStore,
            RedisPushBus,
            RedisRateLimiter,
        )
        from ux_channel.transport.push import set_push_bus

        set_push_bus(RedisPushBus(redis_url))
        return (
            RedisNonceStore(redis_url),
            RedisIdempotencyStore(redis_url),
            RedisRateLimiter(redis_url),
        )
    except ImportError:
        return None, None, None


def create_channel(
    secret: str | None = None,
    *,
    config: Any = None,
    app: Any = None,
    host: Optional[str] = "fastapi",
    path: str = "/ux-channel",
    hub: Any = None,
    renderer: Any = None,
    require_cap: bool = True,
    load_entry_points: bool = False,
    expose_internal_errors: bool = False,
    environment: str = "development",
    install_production_hooks: bool = True,
    redis_url: str | None = None,
    auto_redis: bool = True,
    max_in_flight: int | None = None,
    **registry_kwargs: Any,
) -> Tuple[ActionRegistry, Any]:
    """
    Create ActionRegistry + PluginHub and optionally mount a host.

    Prefer ``config=ChannelConfig.from_env()`` in production.
    Set ``REDIS_URL`` or ``redis_url=`` for multi-worker stores (optional).
    """
    from ux_channel.bridge.plugins import (
        get_hub,
        load_builtin_hosts,
        load_builtin_renderers,
        set_hub,
    )

    hub = hub or get_hub()
    load_builtin_hosts(hub)
    load_builtin_renderers(hub)
    if load_entry_points:
        hub.load_entry_points()

    if redis_url is None and config is not None:
        redis_url = getattr(config, "redis_url", None) or None
    redis_url = redis_url or (os.environ.get("REDIS_URL") if auto_redis else None)
    nonce_store = registry_kwargs.pop("nonce_store", None)
    idempotency_store = registry_kwargs.pop("idempotency_store", None)
    redis_limiter = None
    if auto_redis and redis_url and nonce_store is None:
        ns, ids, rl = _maybe_redis_stores(redis_url)
        nonce_store = ns
        idempotency_store = idempotency_store or ids
        redis_limiter = rl

    env = getattr(config, "environment", environment) if config is not None else environment
    allow_mem = (
        bool(getattr(config, "allow_memory_stores", False))
        if config is not None
        else env != "production"
    )
    # Development and explicit single-worker prod must actually consume once/jti.
    if nonce_store is None and (env != "production" or allow_mem):
        from ux_channel.host.nonce import MemoryNonceStore

        nonce_store = MemoryNonceStore()

    if config is not None:
        env = getattr(config, "environment", "production")
        allow_mem = bool(getattr(config, "allow_memory_stores", False))
        has_durable = bool(
            redis_url or nonce_store is not None or idempotency_store is not None
        )
        if env == "production" and not allow_mem and not has_durable:
            raise ValueError(
                "production Channel requires durable stores: set REDIS_URL / redis_url=, "
                "pass nonce_store/idempotency_store, or set "
                "ChannelConfig(..., allow_memory_stores=True) for single-worker only. "
                "Run: python -m uxchannel check --secret $SECRET"
            )
        reg = ActionRegistry.from_config(
            config,
            renderer=renderer or hub.chain_renderer(),
            install_defaults=install_production_hooks,
            nonce_store=nonce_store,
            idempotency_store=idempotency_store,
            **{k: v for k, v in registry_kwargs.items() if k in ("auth_resolver",)},
        )
        mount_path = getattr(config, "path", path) or path
        mount_config = config
    else:
        if not secret:
            raise ValueError("secret or config is required")
        if environment == "production":
            from ux_channel.host.config import ChannelConfig

            cfg = ChannelConfig.production(
                secret,
                require_cap=require_cap,
                expose_internal_errors=False,
                path=path,
                allow_memory_stores=bool(registry_kwargs.pop("allow_memory_stores", False)),
            )
            # same fail-closed when no redis
            if not cfg.allow_memory_stores and not (
                redis_url or nonce_store or idempotency_store
            ):
                raise ValueError(
                    "production create_channel requires REDIS_URL/redis_url= "
                    "or allow_memory_stores=True"
                )
            reg = ActionRegistry.from_config(
                cfg,
                renderer=renderer or hub.chain_renderer(),
                install_defaults=install_production_hooks,
                nonce_store=nonce_store,
                idempotency_store=idempotency_store,
            )
            mount_path = path
            mount_config = cfg
        else:
            reg = ActionRegistry(
                secret,
                renderer=renderer or hub.chain_renderer(),
                require_cap=require_cap,
                expose_internal_errors=expose_internal_errors,
                nonce_store=nonce_store,
                idempotency_store=idempotency_store,
                **registry_kwargs,
            )
            mount_path = path
            mount_config = None

    if redis_limiter is not None:
        from ux_channel.security.ratelimit import rate_limit_hook

        reg.before(rate_limit_hook(redis_limiter))  # type: ignore[arg-type]

    # CEK Phase 1: Cap adapter (off = no import of cek_host).
    if mount_config is not None and getattr(mount_config, "cek", "off") != "off":
        from ux_channel.cek.host_adapter import apply_host_adapter

        apply_host_adapter(reg, mount_config)

    # Wave 1: WS rate limits + Redis ticket revocation
    if mount_config is not None:
        try:
            from ux_channel.transport.ws_limits import configure_ws_limiter_from_config

            configure_ws_limiter_from_config(mount_config, redis_url=redis_url)
        except Exception:
            import logging

            logging.getLogger("ux_channel.host.factory").exception(
                "ws limiter configure failed (non-fatal; ws rate limits may be off)"
            )
    if redis_url:
        try:
            from ux_channel.devtools.ticket_revoke import (
                RedisRevocationStore,
                TicketRevocationList,
                set_revocation_list,
            )

            set_revocation_list(TicketRevocationList(RedisRevocationStore(redis_url)))
        except Exception:
            import logging

            logging.getLogger("ux_channel.host.factory").exception(
                "ticket revocation list attach failed for redis_url (non-fatal)"
            )

    if app is not None and host:
        # Always pass config when available (FastAPI + Starlette parity)
        if mount_config is not None:
            hub.mount(host, app, reg, path=mount_path, config=mount_config)
        else:
            hub.mount(host, app, reg, path=mount_path)

    # Process concurrency policy from config / kwargs (opt-in/out, defaults on)
    try:
        from ux_channel.transport.concurrency import configure_concurrency, get_concurrency_settings
        from ux_channel.wire import configure_wire as _configure_wire

        cfg_parallel = getattr(config, "parallel_enabled", None) if config is not None else None
        cfg_workers = getattr(config, "max_parallel_workers", None) if config is not None else None
        cfg_min = getattr(config, "parallel_min_items", None) if config is not None else None
        cfg_batch_p = getattr(config, "batch_parallel", None) if config is not None else None
        cfg_batch_lim = getattr(config, "batch_parallel_limit", None) if config is not None else None
        cfg_flight = getattr(config, "max_in_flight", None) if config is not None else None
        # kwargs max_in_flight wins over config
        flight = max_in_flight if max_in_flight is not None else cfg_flight
        # env default for max_in_flight when still None
        if flight is None:
            flight = get_concurrency_settings().max_in_flight
        configure_concurrency(
            parallel_enabled=cfg_parallel,
            max_workers=cfg_workers,
            min_items_for_parallel=cfg_min,
            batch_parallel=cfg_batch_p,
            batch_parallel_limit=cfg_batch_lim,
            max_in_flight=flight,
        )
        max_in_flight = flight
        eng = getattr(config, "wire_engine", None) if config is not None else None
        if eng:
            _configure_wire(engine=eng)
    except Exception:
        pass

    if max_in_flight is not None and max_in_flight > 0:
        from ux_channel.security.bulkhead import install_bulkhead
        install_bulkhead(reg, max_in_flight=max_in_flight)

    # observe=otel → soft-attach OpenTelemetry if installed
    cfg_obs = mount_config or config
    if cfg_obs is not None and str(getattr(cfg_obs, "observe", "") or "").lower() == "otel":
        try:
            from ux_channel.devtools.otel import attach_otel, setup_otel
            from ux_channel.devtools.trace import get_tracer

            setup_otel(service_name="ux_channel")
            ok = attach_otel(get_tracer())
            if not ok:
                import logging

                logging.getLogger("ux_channel.host.factory").warning(
                    "observe=otel but OpenTelemetry attach failed "
                    "(install ux-channel[otel])"
                )
        except Exception as exc:
            import logging

            logging.getLogger("ux_channel.host.factory").warning(
                "observe=otel attach error: %s", exc
            )

    set_hub(hub)
    return reg, hub
