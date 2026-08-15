"""
ChannelConfig — environment-shaped security and limits (**ux-channel** 0.1).

Brand: PyPI ``ux-channel`` · import ``ux_channel`` · CLI ``uxchannel``.

First principles
----------------
Dev defaults that "just work" are hostile in production. This is the single
place that turns environment into policy:

- secret / previous_secrets (cap rotation)
- require_cap, require_channel_header (``X-Channel``)
- rate limits, timeouts, max body sizes
- push/ws tokens, allowed origins
- redis backends, observe flags (``off`` | ``dev`` | ``otel``)

Factories (prefer these over raw ``ChannelConfig(...)``)::

    ChannelConfig.development(secret="...")
    ChannelConfig.production(secret="...", allowed_origins=(...))
    ChannelConfig.from_env()   # UX_CHANNEL_* environment variables

Validation warns on unsafe combinations (memory stores + multi-worker, etc.).

See: ``docs/production/PRODUCTION.md``, ``docs/start/COURSE.md``.
"""
from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass, field, replace
from typing import Optional, Sequence

from ux_channel.security.limits import (
    DEFAULT_MAX_HTML_BYTES,
    DEFAULT_MAX_OPS,
    DEFAULT_MAX_RESULT_BYTES,
)

# Reject trivial secrets in production mode
_WEAK_SECRETS = frozenset(
    {
        "",
        "secret",
        "change-me",
        "dev",
        "dev-only-change-me",
        "test",
        "test-secret",
        "password",
        "x",
    }
)


@dataclass(frozen=True)
class ChannelConfig:
    """
    Immutable production settings for registry + HTTP host.

    Create via ``production()``, ``development()``, or ``from_env()``.
    """

    secret: str
    require_cap: bool = True
    max_cap_age: int = 3600
    max_html_bytes: int = DEFAULT_MAX_HTML_BYTES
    max_ops: int = DEFAULT_MAX_OPS
    max_result_bytes: int = DEFAULT_MAX_RESULT_BYTES
    # Max raw request body (JSON Intent) accepted by hosts
    max_request_bytes: int = 256_000
    # Soft timeout for action handlers (seconds); 0 = disabled
    action_timeout_s: float = 30.0
    # Parallel dispatch policy (opt-in/out; defaults sensible)
    parallel_enabled: bool = True
    max_parallel_workers: int | None = None  # None = auto
    parallel_min_items: int = 2
    batch_parallel: bool = False  # concurrent items inside batch (opt-in)
    batch_parallel_limit: int = 8
    max_in_flight: int | None = None  # bulkhead; None = off
    # Wire JSON codec: auto|orjson|ujson|stdlib (default auto = best available)
    wire_engine: str = "auto"
    # Never leak exception strings to clients in production
    expose_internal_errors: bool = False
    # HTTP
    path: str = "/ux-channel"  # public HTTP mount (never dunder-private)
    allowed_origins: tuple[str, ...] = ()
    # If True and allowed_origins empty, reject cross-site form POSTs with Origin
    enforce_same_origin: bool = True
    # Rate limit (in-memory default; replace with Redis backend for multi-worker)
    rate_limit_per_minute: int = 120
    rate_limit_burst: int = 30
    # Health
    health_list_actions: bool = False  # hide action names on public /health
    # Logging
    log_actions: bool = True
    # Attach intent log + forensics on boot (mutating actions leave a trail)
    audit: bool = False
    # Opt-in file-based regions package (e.g. "app.regions")
    regions: str | tuple[str, ...] | None = None
    regions_auto: bool = True
    regions_strict: bool = True
    # Live inspect (UX/AX/DX); None → on in development, off in production
    inspect_enabled: bool | None = None
    inspect_scope: str = "ops.inspect"
    # Fail when two regions claim the same action wire name
    strict_action_names: bool = True
    # fqn = {uid}.{method} default from Region.mount (already); method = short opt
    action_name_policy: str = "fqn"
    log_slow_ms: float = 200.0
    # Client static cache
    static_max_age: int = 3600
    # Environment label
    environment: str = "production"
    # Wireshark-like action/bridge tracing (dev/staging; off in production())
    trace_enabled: bool = False
    trace_retain: int = 500
    trace_capture_payloads: bool = True
    # Expose /ux-channel/trace HTTP API (never enable on public internet with payloads)
    trace_http: bool = False
    bind_cap_to_principal: bool = False
    require_principal: bool = False
    # Gate GET/POST /trace* when set (Bearer or ?token=)
    trace_token: Optional[str] = None
    trace_sample_rate: float = 1.0
    # Agent / MCP HTTP surface
    agent_token: Optional[str] = None
    mount_agent_mcp: bool = False
    agent_confirmation_secret: Optional[str] = None
    # MCP vertical pack ids (empty = no pack filter)
    mcp_verticals: tuple[str, ...] = ()
    # Claim-bound MCP session TTL (seconds)
    mcp_session_ttl_s: int = 900
    # Region uids exposeable as MCP resources
    mcp_resource_regions: tuple[str, ...] = ()
    # CSRF: require X-Channel on JSON POSTs (production default True)
    require_channel_header: bool = True
    # Cap rotation: older secrets still verify (comma-separated in env)
    previous_secrets: tuple[str, ...] = ()
    # Optional: require X-Channel-Client-Version >= this (ux-channel.js version)
    min_client_version: Optional[str] = None
    # Optional shared secret for GET /ux-channel/push/{topic} (Bearer or ?token=)
    push_token: Optional[str] = None
    # Fail-closed SSE: require ticket, push_token, or public topic (prod default True)
    push_require_auth: bool = True
    # Allow topics under these prefixes without credentials (default public.)
    push_public_prefixes: tuple[str, ...] = ("public.",)
    # When False, public prefixes still need token/ticket
    push_allow_public: bool = True
    # Short-lived subscribe tickets (HMAC via channel secret)
    push_ticket_max_age: int = 300
    push_topic_max_len: int = 128
    # Break-glass: allow all topics without auth (never in production validate)
    push_open: bool = False
    # WebRTC P2P signaling (/ux-channel/rtc) — data plane is browser↔browser
    webrtc_enabled: bool = True
    webrtc_max_peers: int = 8
    webrtc_peer_ttl_s: int = 30
    webrtc_signal_ttl_s: int = 60
    webrtc_require_origin: bool = True
    webrtc_require_ticket: bool = True
    webrtc_ticket_max_age: int = 300
    webrtc_ice_servers: tuple = ()  # optional override list of {urls, username?, credential?}
    webrtc_use_redis: bool | None = None  # None → True when redis_url set
    # Signaling flood control (per peer id, process-local; Redis multi-worker later)
    webrtc_rate_per_minute: int = 180  # poll+signal combined budget
    webrtc_rate_burst: int = 40
    webrtc_min_peer_len: int = 1  # 1=reject empty only; raise in prod if desired
    # WHIP/WHEP demo endpoints (not a full SFU)
    whip_enabled: bool = False
    # External SFU: none | livekit
    sfu_provider: str = "none"
    sfu_url: str = ""
    sfu_api_key: str = ""
    sfu_api_secret: str = ""
    sfu_room_prefix: str = ""
    # None → follow webrtc_require_ticket; True/False override for /sfu/token
    sfu_require_ticket: bool | None = None
    # WebSocket (/ux-channel/ws)
    ws_enabled: bool = True
    ws_allow_actions: bool = True  # Intent dispatch over WS (still requires caps)
    ws_require_origin: bool = False  # if True, reject missing Origin
    ws_max_subscriptions: int = 16
    ws_max_message_bytes: int = 256_000
    # Wave 1: WS rate limits (per IP key / minute)
    ws_connect_per_minute: int = 60
    ws_messages_per_minute: int = 600
    # Wave 1: optional absolute navigate host allowlist (empty = no host filter)
    navigate_allowed_hosts: tuple[str, ...] = ()
    # Wave 5: optional tenant topic prefix enforced on private topics
    tenant_topic_prefix: str = ""
    allow_memory_stores: bool = False
    redis_url: Optional[str] = None
    # Unified observability: off | dev | otel  (maps to trace flags)
    observe: str = "off"
    # Architecture opt-ins (ADR 0002/0005). Classic floor when peer lacks hello.
    effects: str = "auto"  # auto | classic
    proofs: str = "auto"  # auto | require | off
    flow: str = "auto"  # auto | off  (meta.flow_id = correlation only)
    proof_secret: Optional[str] = None
    # CEK drop-in (Phase 1). off = today's path (zero new imports).
    # adapt = extra [cek] live, Channel Cap remains authority.
    # require = Cap + enhance compose go through cek-host / cek-surface.
    cek: str = "off"
    # Morph / toast HTML policy: off (default, ux-dom safe) | strict (strip script/on*).
    # Production factory leaves this off so ux-dom is not broken; doctor warns.
    morph_html_policy: str = "off"

    def validate(self) -> "ChannelConfig":
        """Raise ValueError if config is unsafe for declared environment."""
        obs = (self.observe or "off").lower()
        if obs not in ("off", "dev", "otel"):
            raise ValueError("observe must be off|dev|otel")
        if self.effects not in ("auto", "classic"):
            raise ValueError('effects must be "auto" or "classic"')
        if self.proofs not in ("auto", "require", "off"):
            raise ValueError('proofs must be "auto", "require", or "off"')
        if self.flow not in ("auto", "off"):
            raise ValueError('flow must be "auto" or "off"')
        from ux_channel.cek.config import parse_cek

        object.__setattr__(self, "cek", parse_cek(self.cek))
        policy = (self.morph_html_policy or "off").lower()
        if policy not in ("off", "strict"):
            raise ValueError('morph_html_policy must be "off" or "strict"')
        object.__setattr__(self, "morph_html_policy", policy)
        if self.proof_secret is not None:
            if self.proof_secret == self.secret:
                raise ValueError("proof_secret must differ from cap secret")
            if len(self.proof_secret) < 16:
                raise ValueError("proof_secret must be at least 16 characters")
        if self.proofs == "require" and not self.proof_secret:
            raise ValueError("proofs=require needs proof_secret (separate from cap secret)")
        if self.environment == "production":
            if self.secret in _WEAK_SECRETS or len(self.secret) < 32:
                raise ValueError(
                    "ChannelConfig.production requires secret length >= 32 "
                    "and not a known weak placeholder. "
                    "Generate with: secrets.token_urlsafe(48)"
                )
            if self.expose_internal_errors:
                raise ValueError(
                    "expose_internal_errors must be False in production"
                )
            if not self.require_cap:
                warnings.warn(
                    "require_cap=False in production is dangerous",
                    stacklevel=2,
                )
            if self.trace_enabled and self.trace_capture_payloads:
                warnings.warn(
                    "trace_capture_payloads=True in production may record PII",
                    stacklevel=2,
                )
            if self.mount_agent_mcp and not self.agent_token:
                raise ValueError(
                    "mount_agent_mcp=True in production requires agent_token "
                    "(UX_CHANNEL_AGENT_TOKEN)"
                )
            if not self.require_channel_header:
                warnings.warn(
                    "require_channel_header=False weakens CSRF protection",
                    stacklevel=2,
                )
            if self.allow_memory_stores:
                warnings.warn(
                    "allow_memory_stores=True: once-caps/idempotency are process-local "
                    "and unsafe across multiple workers",
                    stacklevel=2,
                )
            if self.push_open:
                raise ValueError(
                    "push_open=True is not allowed in production "
                    "(refuses fail-open SSE subscribe)"
                )
            if (
                self.push_require_auth
                and not self.push_token
                and not self.push_allow_public
            ):
                warnings.warn(
                    "push_require_auth without push_token and public prefixes disabled: "
                    "only signed push tickets will authorize SSE",
                    stacklevel=2,
                )
            if self.webrtc_enabled and not self.webrtc_require_ticket:
                warnings.warn(
                    "webrtc_require_ticket=False in production: rooms are joinable "
                    "by anyone who knows the room id — prefer sign_ticket()",
                    stacklevel=2,
                )
            if self.webrtc_enabled and not self.webrtc_require_origin:
                warnings.warn(
                    "webrtc_require_origin=False weakens RTC CSRF protection",
                    stacklevel=2,
                )
        elif len(self.secret) < 8:
            raise ValueError("secret too short even for development")
        if self.max_request_bytes < 1024:
            raise ValueError("max_request_bytes too small")
        if self.action_timeout_s < 0:
            raise ValueError("action_timeout_s must be >= 0")
        return self

    @classmethod
    def production(cls, secret: str, **kwargs) -> "ChannelConfig":
        """Fail-closed production defaults.

        WebRTC P0: private rooms require tickets unless caller overrides
        ``webrtc_require_ticket=False``.

        Audit trail on by default (intent log + forensics).
        WebSocket Origin required (browsers always send it; service clients
        may set ``ws_require_origin=False``).

        When ``allowed_origins`` is set and ``navigate_allowed_hosts`` is not,
        hostnames are derived so absolute navigate/push_url cannot open-redirect
        off-site (relative paths remain allowed).
        """
        kwargs.setdefault("audit", True)
        kwargs.setdefault("webrtc_require_ticket", True)
        kwargs.setdefault("webrtc_require_origin", True)
        kwargs.setdefault("ws_require_origin", True)
        # Derive navigate host allowlist from browser origins when not explicit.
        if (
            "navigate_allowed_hosts" not in kwargs
            and kwargs.get("allowed_origins")
            and not kwargs.get("navigate_allowed_hosts")
        ):
            from urllib.parse import urlparse

            hosts: list[str] = []
            for origin in kwargs.get("allowed_origins") or ():
                try:
                    h = (urlparse(str(origin)).hostname or "").lower()
                except Exception:
                    h = ""
                if h and h not in hosts:
                    hosts.append(h)
            if hosts:
                kwargs["navigate_allowed_hosts"] = tuple(hosts)
        # observe defaults off; allow_memory_stores must be explicit
        # Stolen-cap residual: shorter default TTL (15 min) unless caller set one.
        kwargs.setdefault("max_cap_age", 900)
        return cls(secret=secret, environment="production", **kwargs).validate()

    @classmethod
    def development(cls, secret: str = "", **kwargs) -> "ChannelConfig":
        """Local DX defaults; generates a secret if omitted."""
        sec = secret or ("dev-" + secrets.token_urlsafe(24))
        kw = {
            "expose_internal_errors": True,
            "health_list_actions": True,
            "rate_limit_per_minute": 120_000,  # high for local/demo stress
            "rate_limit_burst": 50_000,
            "environment": "development",
            "trace_enabled": True,
            "trace_http": True,
            "trace_capture_payloads": True,
            "require_channel_header": False,
            "allow_memory_stores": True,
            "observe": "dev",
            "push_require_auth": False,
            "webrtc_require_ticket": False,
            "webrtc_require_origin": False,
            **kwargs,
        }
        # map observe → trace
        obs = str(kw.get("observe", "dev")).lower()
        if obs == "off":
            kw["trace_enabled"] = False
            kw["trace_http"] = False
        elif obs in ("dev", "otel"):
            kw["trace_enabled"] = True
            kw["trace_http"] = True
        return cls(secret=sec, **kw).validate()

    @classmethod
    def from_env(cls, prefix: str | None = None) -> "ChannelConfig":
        """
        Load from environment variables.

        Default prefix is ``UX_CHANNEL_`` (brand). Pass ``prefix=`` only for
        unusual multi-tenant env layouts.

        Required in production: ``UX_CHANNEL_SECRET`` (≥32 chars)
        Optional: ``UX_CHANNEL_ENV`` = production|development
        """
        if prefix is None:
            prefix = "UX_CHANNEL_"
        if not prefix.endswith("_"):
            prefix = prefix + "_"
        env = os.environ.get(f"{prefix}ENV", "production").lower()
        secret = os.environ.get(f"{prefix}SECRET", "")
        if not secret and env == "development":
            return cls.development()
        if not secret:
            raise ValueError(f"{prefix}SECRET environment variable is required")

        def _int(name: str, default: int) -> int:
            raw = os.environ.get(f"{prefix}{name}")
            return int(raw) if raw else default

        def _float(name: str, default: float) -> float:
            raw = os.environ.get(f"{prefix}{name}")
            return float(raw) if raw else default

        origins = os.environ.get(f"{prefix}ALLOWED_ORIGINS", "")
        origin_t = tuple(o.strip() for o in origins.split(",") if o.strip())

        base = {
            "secret": secret,
            "require_cap": os.environ.get(f"{prefix}REQUIRE_CAP", "1") not in ("0", "false"),
            "max_cap_age": _int("MAX_CAP_AGE", 3600),
            "max_html_bytes": _int("MAX_HTML_BYTES", DEFAULT_MAX_HTML_BYTES),
            "max_ops": _int("MAX_OPS", DEFAULT_MAX_OPS),
            "max_result_bytes": _int("MAX_RESULT_BYTES", DEFAULT_MAX_RESULT_BYTES),
            "max_request_bytes": _int("MAX_REQUEST_BYTES", 256_000),
            "action_timeout_s": _float("ACTION_TIMEOUT_S", 30.0),
            "expose_internal_errors": os.environ.get(f"{prefix}EXPOSE_ERRORS", "0")
            in ("1", "true"),
            "path": os.environ.get(f"{prefix}PATH", "/ux-channel"),
            "allowed_origins": origin_t,
            "rate_limit_per_minute": _int("RATE_LIMIT_PER_MINUTE", 120),
            "rate_limit_burst": _int("RATE_LIMIT_BURST", 30),
            "health_list_actions": os.environ.get(f"{prefix}HEALTH_LIST_ACTIONS", "0")
            in ("1", "true"),
            "environment": env if env in ("production", "development") else "production",
            "trace_enabled": os.environ.get(f"{prefix}TRACE", "0") in ("1", "true"),
            "trace_http": os.environ.get(f"{prefix}TRACE_HTTP", "0") in ("1", "true"),
            "trace_capture_payloads": os.environ.get(f"{prefix}TRACE_PAYLOADS", "1")
            not in ("0", "false"),
            "trace_token": os.environ.get(f"{prefix}TRACE_TOKEN") or None,
            "trace_sample_rate": float(os.environ.get(f"{prefix}TRACE_SAMPLE", "1") or 1),
            "agent_token": os.environ.get(f"{prefix}AGENT_TOKEN") or None,
            "mount_agent_mcp": os.environ.get(f"{prefix}MOUNT_AGENT_MCP", "0") in ("1", "true"),
            "mcp_verticals": tuple(
                x.strip() for x in (os.environ.get(f"{prefix}MCP_VERTICALS") or "").split(",") if x.strip()
            ),
            "mcp_session_ttl_s": int(os.environ.get(f"{prefix}MCP_SESSION_TTL_S") or "900"),
            "mcp_resource_regions": tuple(
                x.strip() for x in (os.environ.get(f"{prefix}MCP_RESOURCE_REGIONS") or "").split(",") if x.strip()
            ),
            "agent_confirmation_secret": os.environ.get(f"{prefix}AGENT_CONFIRM") or None,
            "require_channel_header": os.environ.get(f"{prefix}REQUIRE_CHANNEL_HEADER", "1")
            not in ("0", "false"),
            "previous_secrets": tuple(
                s.strip() for s in (os.environ.get(f"{prefix}PREVIOUS_SECRETS") or "").split(",")
                if s.strip()
            ),
            "min_client_version": os.environ.get(f"{prefix}MIN_CLIENT_VERSION") or None,
            "push_token": os.environ.get(f"{prefix}PUSH_TOKEN") or None,
            "push_require_auth": os.environ.get(f"{prefix}PUSH_REQUIRE_AUTH", "1")
            not in ("0", "false")
            if env == "production"
            else os.environ.get(f"{prefix}PUSH_REQUIRE_AUTH", "0") in ("1", "true"),
            "push_public_prefixes": tuple(
                p.strip()
                for p in (
                    os.environ.get(f"{prefix}PUSH_PUBLIC_PREFIXES") or "public."
                ).split(",")
                if p.strip()
            ),
            "push_allow_public": os.environ.get(f"{prefix}PUSH_ALLOW_PUBLIC", "1")
            not in ("0", "false"),
            "push_ticket_max_age": _int("PUSH_TICKET_MAX_AGE", 300),
            "push_topic_max_len": _int("PUSH_TOPIC_MAX_LEN", 128),
            "push_open": os.environ.get(f"{prefix}PUSH_OPEN", "0") in ("1", "true"),
            "ws_enabled": os.environ.get(f"{prefix}WS_ENABLED", "1") not in ("0", "false"),
            "ws_allow_actions": os.environ.get(f"{prefix}WS_ALLOW_ACTIONS", "1")
            not in ("0", "false"),
            "ws_require_origin": os.environ.get(
                f"{prefix}WS_REQUIRE_ORIGIN",
                "1" if env == "production" else "0",
            )
            in ("1", "true"),
            "ws_max_subscriptions": _int("WS_MAX_SUBSCRIPTIONS", 16),
            "ws_max_message_bytes": _int("WS_MAX_MESSAGE_BYTES", 256_000),
            "ws_connect_per_minute": _int("WS_CONNECT_PER_MINUTE", 60),
            "ws_messages_per_minute": _int("WS_MESSAGES_PER_MINUTE", 600),
            "navigate_allowed_hosts": tuple(
                h.strip().lower()
                for h in (os.environ.get(f"{prefix}NAVIGATE_ALLOWED_HOSTS") or "").split(",")
                if h.strip()
            ),
            "tenant_topic_prefix": os.environ.get(f"{prefix}TENANT_TOPIC_PREFIX") or "",
            "allow_memory_stores": os.environ.get(f"{prefix}ALLOW_MEMORY_STORES", "0")
            in ("1", "true"),
            "redis_url": os.environ.get("REDIS_URL") or os.environ.get(f"{prefix}REDIS_URL") or None,
            "observe": os.environ.get(f"{prefix}OBSERVE", "off" if env == "production" else "dev"),
            "effects": os.environ.get(f"{prefix}EFFECTS", "auto"),
            "proofs": os.environ.get(f"{prefix}PROOFS", "auto"),
            "flow": os.environ.get(f"{prefix}FLOW", "auto"),
            "proof_secret": os.environ.get(f"{prefix}PROOF_SECRET") or None,
            "cek": os.environ.get(f"{prefix}CEK", "off"),
            "morph_html_policy": os.environ.get(f"{prefix}MORPH_HTML_POLICY", "off"),
        }
        if base["environment"] == "development":
            base.setdefault("allow_memory_stores", True)
            if base.get("observe") == "off" and not os.environ.get(f"{prefix}OBSERVE"):
                base["observe"] = "dev"
            return cls.development(**{k: v for k, v in base.items() if k != "environment"})  # type: ignore[arg-type]
        return cls.production(**{k: v for k, v in base.items() if k != "environment"})  # type: ignore[arg-type]

    def with_secret(self, secret: str) -> "ChannelConfig":
        return replace(self, secret=secret).validate()

    def with_redis(self, redis_url: str | None = None) -> "ChannelConfig":
        """
        Attach Redis URL and force durable stores (allow_memory_stores=False).

        ``Channel.boot`` / ``create_channel`` read ``config.redis_url`` when
        the ``redis_url=`` argument is omitted.
        """
        import os

        url = redis_url or self.redis_url or os.environ.get("REDIS_URL")
        if not url:
            raise ValueError(
                "with_redis() needs redis_url= or REDIS_URL env "
                "(or config.redis_url already set)"
            )
        return replace(self, allow_memory_stores=False, redis_url=str(url)).validate()

    def with_navigate_hosts(self, *hosts: str) -> "ChannelConfig":
        """Allow only these hosts for absolute http(s) navigate/push_url."""
        cleaned = tuple(h.strip().lower() for h in hosts if h and h.strip())
        return replace(self, navigate_allowed_hosts=cleaned).validate()
