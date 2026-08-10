"""
Media plane bridge — mesh + battle-tested SFU (LiveKit) as one Developer tooling.

Philosophy
----------
* **ux-channel** authorizes and places plugins; it does **not** move media bytes.
* **mesh** → existing WebRTC ferry (``ch.webrtc`` / ``ux-webrtc.js``).
* **sfu** → external stack millions use (default **LiveKit** + ``livekit-client`` on the host).
* **No call UI chrome** — only placement bags (strings/dicts).

Application::

    p = ch.media.plugin("lobby", sub=user_id)          # auto: sfu if configured else mesh
    p = ch.media.plugin("lobby", sub=user_id, mode="mesh")
    p = ch.media.plugin("lobby", sub=user_id, mode="sfu")  # LiveKit token bag

    # power
    ch.media.mesh   # WebRTCPlane
    ch.media.sfu    # SfuBridge (tokens + plugin)

Host places **Placement data** (``p.scripts``, ``p.attrs``, ``p.client``).
HTML strings are only via ``ux_channel.render.kit.script_tags`` / ``attr_string``.
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any, Literal, Mapping, Optional

from ux_channel.render.placement import Placement
from ux_channel.realtime.sfu import SfuAdapter, get_sfu

MediaMode = Literal["auto", "mesh", "sfu"]

__all__ = [
    "MediaPlane",
    "MediaPlugin",
    "SfuBridge",
    "attach_media",
    "MEDIA_PUBLIC_API",
]

MEDIA_PUBLIC_API = (
    "plugin",  # only placement entry
    "mode",
    "diagnose",
    "ice",
)
# Power: .mesh / .sfu adapters — not application names


def _esc(s: object) -> str:
    return escape(str(s), quote=True)


def _attrs_to_py(attrs: Mapping[str, str]) -> dict[str, str]:
    return {k.replace("-", "_"): v for k, v in attrs.items()}


@dataclass(frozen=True)
class MediaPlugin:
    """
    Media placement — **data only** (extends Placement fields).

    Primary truth: ``scripts`` (URLs), ``attrs`` (dict), ``client`` (dict).
    Use ``ux_channel.render.kit.script_tags`` / ``attr_string`` for demo markup.
    """

    mode: str
    provider: str
    room: str
    attrs: dict[str, str]
    client: dict[str, Any]
    scripts: tuple = ()
    path: str = ""
    ticket: Optional[str] = None
    token: Optional[str] = None
    # optional demo HTML string; prefer demo.script_tags(p)
    _scripts_html: str = ""
    _attr_string: str = ""

    @property
    def client_json(self) -> str:
        return _serde.dumps(self.client)

    @property
    def attrs_py(self) -> dict[str, str]:
        return {k.replace("-", "_"): v for k, v in self.attrs.items()}

    @property
    def scripts_html(self) -> str:
        """Demo convenience — prefer ``ux_channel.render.kit.script_tags(self)``."""
        from ux_channel.render.kit import script_tags

        if self._scripts_html:
            return self._scripts_html
        return script_tags(self.scripts)

    @property
    def attr_string(self) -> str:
        from ux_channel.render.kit import attr_string

        if self._attr_string:
            return self._attr_string
        return attr_string(self.attrs)

    def to_placement(self) -> "Placement":
        from ux_channel.render.placement import Placement

        return Placement(
            attrs=dict(self.attrs),
            client=dict(self.client),
            scripts=tuple(self.scripts),
            path=self.path,
            kind="media",
            meta={
                "mode": self.mode,
                "provider": self.provider,
                "room": self.room,
                "ticket": self.ticket,
                "token": self.token,
            },
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "provider": self.provider,
            "room": self.room,
            "attrs": dict(self.attrs),
            "attrs_py": self.attrs_py,
            "client": dict(self.client),
            "client_json": self.client_json,
            "scripts": [
                s.as_dict() if hasattr(s, "as_dict") else s for s in self.scripts
            ],
            "path": self.path,
            "ticket": self.ticket,
            "token": self.token,
            # omit scripts_html/attr_string from primary dict (no HTML truth)
        }


@dataclass
class SfuBridge:
    """
    Thin bridge to external SFU (LiveKit by default).

    Does not embed livekit-client source — host uses npm/CDN; we mint tokens
    and emit a placement bag + optional CDN script tags.
    """

    channel: Any

    def adapter(self) -> SfuAdapter:
        return get_sfu(getattr(self.channel, "config", None))

    def configured(self) -> bool:
        cfg = getattr(self.channel, "config", None)
        prov = (getattr(cfg, "sfu_provider", None) or "none").lower()
        return prov not in ("", "none", "mesh")

    def provider_name(self) -> str:
        cfg = getattr(self.channel, "config", None)
        return (getattr(cfg, "sfu_provider", None) or "none").lower()

    def create_token(
        self,
        room: str,
        *,
        identity: str,
        name: str = "",
        can_publish: bool = True,
        can_subscribe: bool = True,
        ttl_s: int = 3600,
    ) -> str:
        return self.adapter().create_token(
            room=room,
            identity=identity,
            name=name,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
            ttl_s=ttl_s,
        )

    def room_url(self, room: str = "default") -> str:
        return self.adapter().room_url(room)

    def plugin(
        self,
        room: str = "default",
        *,
        sub: str = "",
        name: str = "",
        can_publish: bool = True,
        can_subscribe: bool = True,
        ttl_s: int = 3600,
        cdn: bool = True,
        livekit_client_version: str = "2.9.1",
        inspector: bool = False,
    ) -> MediaPlugin:
        """
        LiveKit (or configured SFU) placement bag.

        ``client`` keys for host / livekit-client::

            { provider, url, token, room, identity, canPublish, canSubscribe }
        """
        room = (room or "default").strip() or "default"
        identity = (sub or name or "user").strip() or "user"
        if not self.configured():
            raise RuntimeError(
                "SFU not configured (sfu_not_configured). "
                "Set LIVEKIT_URL + LIVEKIT_API_KEY + LIVEKIT_API_SECRET "
                "(sfu_provider='livekit') or use mode='mesh'. "
                "Channel.help('media-sfu') · uxchannel recipe media-sfu"
            )
        token = self.create_token(
            room,
            identity=identity,
            name=name or identity,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
            ttl_s=ttl_s,
        )
        url = self.room_url(room)
        provider = self.provider_name()
        client = {
            "provider": provider,
            "url": url,
            "token": token,
            "room": room,
            "identity": identity,
            "canPublish": can_publish,
            "canSubscribe": can_subscribe,
        }
        attrs = {
            "data-channel-media-mode": "sfu",
            "data-channel-media-provider": provider,
            "data-channel-media-room": room,
            "data-channel-media-url": url,
            # token in attr is convenient for demos; prefer client_json in production HTML
            "data-channel-media-identity": identity,
        }
        # Prefer token only in client_json / script type=application/json — still allow
        # optional attr when host wants data-* (document XSS risk if page XSS'd)
        script_refs, scripts_html = self._script_refs(
            cdn=cdn,
            livekit_client_version=livekit_client_version,
            client=client,
            inspector=inspector,
        )
        return MediaPlugin(
            mode="sfu",
            provider=provider,
            room=room,
            attrs=attrs,
            client=client,
            scripts=tuple(script_refs),
            path=url,
            token=token,
            _scripts_html=scripts_html,
            _attr_string=" ".join(f'{k}="{_esc(v)}"' for k, v in attrs.items()),
        )

    def _script_refs(
        self,
        *,
        cdn: bool,
        livekit_client_version: str,
        client: dict[str, Any],
        inspector: bool,
    ) -> tuple[list, str]:
        """Return (ScriptRef list, demo HTML string). Data list is the truth."""
        from ux_channel.render.placement import ScriptRef

        ch = self.channel
        base = (getattr(ch, "path", None) or "/ux-channel").rstrip("/")
        refs: list = [
            ScriptRef(src=f"{base}/static/ux-channel.js", defer=True, id="ux-channel"),
            ScriptRef(src=f"{base}/static/ux-bridge.js", defer=True, id="ux-bridge"),
        ]
        if inspector:
            refs.append(
                ScriptRef(src=f"{base}/static/ux-inspector.js", defer=True, id="ux-inspector")
            )
        if cdn and self.provider_name() == "livekit":
            ver = livekit_client_version
            refs.append(
                ScriptRef(
                    src=f"https://cdn.jsdelivr.net/npm/livekit-client@{ver}/dist/livekit-client.umd.js",
                    defer=True,
                    id="livekit-client",
                )
            )
            refs.append(
                ScriptRef(
                    src=f"{base}/static/ux-sfu-livekit.js",
                    defer=True,
                    id="ux-sfu-livekit",
                )
            )
        # Demo HTML (not truth) — client JSON embedded for boot
        from ux_channel.render.kit import script_tags

        html = script_tags(refs)
        html += (
            '\n<script type="application/json" id="ux-media-client">'
            f"{_serde.dumps(client)}"
            "</script>"
        )
        return refs, html

    def diagnose(self) -> dict[str, Any]:
        cfg = getattr(self.channel, "config", None)
        return {
            "configured": self.configured(),
            "provider": self.provider_name(),
            "url_set": bool(getattr(cfg, "sfu_url", "") if cfg else ""),
            "token_endpoint": f"{getattr(self.channel, 'path', '/ux-channel')}/sfu/token",
            "note": "Media bytes run on external SFU; channel only mints tokens",
        }


class MediaPlane:
    """
    Unified media DX: mesh (built-in) + SFU bridges (LiveKit, …).

    Attached as ``ch.media`` at boot.
    """

    def __init__(self, channel: Any) -> None:
        self.channel = channel
        self._sfu = SfuBridge(channel)

    # --- application properties --------------------------------------------------

    @property
    def mesh(self) -> Any:
        """Built-in mesh plane (``ch.webrtc``)."""
        return getattr(self.channel, "webrtc", None)

    @property
    def sfu(self) -> SfuBridge:
        return self._sfu

    @property
    def ice(self) -> Any:
        """Mesh ICE helper (``ch.webrtc.ice``); SFU uses provider ICE."""
        w = self.mesh
        return getattr(w, "ice", None) if w is not None else None

    @property
    def mode(self) -> str:
        """Resolved default: sfu if configured else mesh."""
        return "sfu" if self._sfu.configured() else "mesh"

    def resolve_mode(self, mode: MediaMode | str | None = None) -> str:
        m = (mode or "auto").lower().strip()
        if m in ("", "auto"):
            return self.mode
        if m in ("mesh", "sfu"):
            return m
        raise ValueError("mode must be auto|mesh|sfu")

    def plugin(
        self,
        room: str = "default",
        *,
        sub: str = "",
        mode: MediaMode | str | None = "auto",
        **kwargs: Any,
    ) -> MediaPlugin:
        """
        One call for hosts — mesh or SFU placement bag.

        ::

            p = ch.media.plugin("lobby", sub=user_id)
            # p.attrs, p.client, p.scripts  — data only
            # demo: ux_channel.render.kit.script_tags(p) / attr_string(p)
        """
        resolved = self.resolve_mode(mode)
        if resolved == "sfu":
            return self._sfu.plugin(room, sub=sub, **kwargs)
        return self._mesh_plugin(room, sub=sub, **kwargs)


    def _mesh_plugin(
        self,
        room: str,
        *,
        sub: str = "",
        inspector: bool = False,
        **kwargs: Any,
    ) -> MediaPlugin:
        w = self.mesh
        if w is None:
            raise RuntimeError("WebRTC mesh plane not attached (webrtc_enabled?)")
        # Strip SFU-only kwargs
        for k in (
            "cdn",
            "livekit_client_version",
            "can_publish",
            "can_subscribe",
            "ttl_s",
            "name",
        ):
            kwargs.pop(k, None)
        p = w.plugin(room, sub=sub, inspector=inspector, **kwargs)
        d = p.as_dict() if hasattr(p, "as_dict") else {}
        client = dict(d.get("client") or p.client)
        client["provider"] = "mesh"
        client["mode"] = "mesh"
        attrs = dict(d.get("attrs") or p.attrs)
        attrs["data-channel-media-mode"] = "mesh"
        attrs["data-channel-media-provider"] = "mesh"
        from ux_channel.render.placement import ScriptRef

        base = (getattr(self.channel, "path", None) or "/ux-channel").rstrip("/")
        refs = [
            ScriptRef(src=f"{base}/static/ux-channel.js", defer=True),
            ScriptRef(src=f"{base}/static/ux-webrtc.js", defer=True),
        ]
        path = str(d.get("path") or getattr(w, "path", "") or f"{base}/rtc")
        ticket = d.get("ticket") if isinstance(d, dict) else getattr(p, "ticket", None)
        return MediaPlugin(
            mode="mesh",
            provider="mesh",
            room=room,
            attrs=attrs,
            client=client,
            scripts=tuple(refs),
            path=path,
            ticket=ticket,
            _attr_string=" ".join(f'{k}="{_esc(v)}"' for k, v in attrs.items()),
        )

    def diagnose(self) -> dict[str, Any]:
        mesh_d = {}
        w = self.mesh
        if w is not None and hasattr(w, "diagnose"):
            mesh_d = w.diagnose()
        return {
            "default_mode": self.mode,
            "mesh": mesh_d,
            "sfu": self._sfu.diagnose(),
            "public_api": list(MEDIA_PUBLIC_API),
            "boundary": "channel places plugins; SFU/mesh transport owns media bytes",
        }


def attach_media(channel: Any) -> MediaPlane:
    """Attach ``channel.media`` (called from Channel boot)."""
    plane = MediaPlane(channel)
    channel.media = plane
    return plane
