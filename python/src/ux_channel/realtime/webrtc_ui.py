"""
WebRTC **plugin** surface — framework-agnostic, no UI chrome.

Mission (ux-channel)
---------------------
Channel owns **signaling, tickets, client runtime URL, ICE public config**.
Hosts own **all markup** (video tags, buttons, CSS, layout).

This module never ships call-room HTML/CSS/widgets. That bloat belongs in
examples or the app — not the library.

Placement contract (only)::

    s = ch.webrtc.session("lobby", sub=user_id)
    p = s.plugin()
    # host:
    #   <head>  {p.scripts_html}
    #   <body {p.attr_string}>  …your UI…
    #   UxWebRTC.join(p.client)  // or read body data-* 

``p.client`` is the JSON opts dict for ``UxWebRTC.join``.

ICE (automatic in plugin)
-------------------------
* ``client["iceServers"]`` = ``ice.servers()`` (STUN only)
* ``client["iceUrl"]`` = ``ice.url`` (browser loads TURN with ticket)
Hosts do not place TURN passwords. Flexible: skip ``iceUrl`` fetch or pass
custom ``iceServers`` in ``extra_client`` if you mint elsewhere.
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

from dataclasses import dataclass, field
from html import escape
from typing import Any, Literal, Mapping, Optional

MediaMode = Literal["none", "audio", "video", "av", True, False]

__all__ = ["RtcSession", "RtcPlugin", "media_to_client", "attrs_to_py"]


def media_to_client(media: MediaMode) -> Any:
    """Map session media hint → client ``media`` option (or None)."""
    if media is True or media == "av":
        return {"audio": True, "video": True}
    if media is False or media == "none" or media is None:
        return None
    if media == "audio":
        return {"audio": True, "video": False}
    if media == "video":
        return {"audio": False, "video": True}
    return media


def attrs_to_py(attrs: Mapping[str, str]) -> dict[str, str]:
    """``data-*`` → ``data_*`` for Python kwargs DSLs (any framework)."""
    return {k.replace("-", "_"): v for k, v in attrs.items()}


def _esc(s: object) -> str:
    return escape(str(s), quote=True)


@dataclass(frozen=True)
class RtcPlugin:
    """Immutable host bag — strings/dicts only, no widgets."""

    room: str
    scripts_html: str
    attrs: dict[str, str]
    attr_string: str
    attrs_py: dict[str, str]
    client: dict[str, Any]
    path: str
    ws_path: str
    ticket: Optional[str] = None

    @property
    def client_json(self) -> str:
        """Compact JSON for host-owned <script> embeds (not a UI widget)."""
        import json

        return _serde.dumps(self.client)

    def as_dict(self) -> dict[str, Any]:
        return {
            "room": self.room,
            "scripts_html": self.scripts_html,
            "attrs": dict(self.attrs),
            "attr_string": self.attr_string,
            "attrs_py": dict(self.attrs_py),
            "client": dict(self.client),
            "client_json": self.client_json,
            "path": self.path,
            "ws_path": self.ws_path,
            "ticket": self.ticket,
        }


@dataclass
class RtcSession:
    """Room-scoped signaling plugin (no markup)."""

    plane: Any
    room: str = "lobby"
    ticket: Optional[str] = None
    sub: str = ""
    # client join hints (not HTML)
    media: MediaMode = "none"
    auto_media: bool = False
    simulcast: bool = False
    ice_policy: Literal["all", "relay"] = "all"
    extra_client: dict[str, Any] = field(default_factory=dict)

    def ensure_ticket(self) -> Optional[str]:
        if self.ticket:
            return self.ticket
        cfg = getattr(self.plane.channel, "config", None)
        if cfg is not None and getattr(cfg, "webrtc_require_ticket", False):
            self.ticket = self.plane.sign_ticket(self.room, sub=self.sub)
        return self.ticket

    def client_options(self) -> dict[str, Any]:
        """Opts for ``UxWebRTC.join`` — host wires this in their own JS/UI.

        Wire keys (stable)::

            room, rtcPath, wsPath, iceServers (html), iceUrl (live),
            iceTransportPolicy, simulcast, ticket?, media?, mediaHint?
        """
        self.ensure_ticket()
        opts: dict[str, Any] = {
            "room": self.room,
            "rtcPath": self.plane.path,
            "wsPath": self.plane.ws_path,
            "iceServers": self.plane.ice.servers(),  # public seed
            "iceUrl": self.plane.ice.url,  # ticketed live TURN
            "iceTransportPolicy": self.ice_policy,
            "simulcast": bool(self.simulcast),
        }
        if self.ticket:
            opts["ticket"] = self.ticket
        m = media_to_client(self.media if self.auto_media else "none")
        if m:
            opts["media"] = m
        # If media hint set but not auto_media, still expose under "mediaHint"
        # so hosts can decide when to startMedia — does not auto-gUM.
        hint = media_to_client(self.media)
        if hint and not self.auto_media:
            opts["mediaHint"] = hint
        opts.update(self.extra_client)
        return opts

    def attrs(self) -> dict[str, str]:
        """``data-channel-webrtc-*`` for the document body (placement only)."""
        self.ensure_ticket()
        return self.plane.body_attrs(
            room=self.room,
            auto=False,
            media=False,
            ticket=self.ticket,
            prefer_ws=True,
        )

    def attr_string(self) -> str:
        return " ".join(f'{k}="{_esc(v)}"' for k, v in self.attrs().items())

    def attrs_py(self) -> dict[str, str]:
        return attrs_to_py(self.attrs())

    def scripts_html(self, *, inspector: bool = False) -> str:
        """Demo HTML only — prefer Placement.scripts via ch.media / ch.runtime."""
        from ux_channel.render.kit import script_tags

        ch = self.plane.channel
        if hasattr(ch, "runtime"):
            return script_tags(ch.runtime(inspector=inspector, webrtc=True))
        return ""

    def plugin(self, *, inspector: bool = False) -> RtcPlugin:
        self.ensure_ticket()
        a = self.attrs()
        return RtcPlugin(
            room=self.room,
            scripts_html=self.scripts_html(inspector=inspector),
            attrs=dict(a),
            attr_string=self.attr_string(),
            attrs_py=attrs_to_py(a),
            client=self.client_options(),
            path=self.plane.path,
            ws_path=self.plane.ws_path,
            ticket=self.ticket,
        )

    # thin aliases
    def body_attrs(self) -> dict[str, str]:
        return self.attrs()

    def body_attr_string(self) -> str:
        return self.attr_string()
