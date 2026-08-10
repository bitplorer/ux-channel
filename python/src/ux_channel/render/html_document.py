"""
Document / runtime **Placement** for Channel (no HTML strings).

ux-dom and templates consume ``ch.runtime().scripts`` and ``ch.body_attrs()``.
Demo HTML lives only in ``ux_channel.render.kit``.

Region SSR is separate: ``ch.html(uid)`` from RegionBook (see flow.attach_flow).
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

from typing import Any, Mapping, Optional

__all__ = ["attach_document"]


def attach_document(channel: Any) -> None:
    """Attach ``runtime`` + ``body_attrs`` (data only). Do not touch ``ch.html`` (region SSR)."""

    def _env_flags(dev: bool | None, inspector: bool | None) -> tuple[bool, bool]:
        env = getattr(channel.config, "environment", None) if channel.config else None
        if dev is None:
            dev = env == "development"
        if inspector is None:
            inspector = bool(dev)
        return bool(dev), bool(inspector)

    def runtime(
        *,
        bridge: bool = True,
        inspector: bool | None = None,
        dev: bool | None = None,
        webrtc: bool | None = None,
    ):
        """Channel runtime Placement (script URLs) — no HTML."""
        from ux_channel.render.placement import Placement, ScriptRef

        dev_b, insp = _env_flags(dev, inspector)
        base = channel.path.rstrip("/")
        refs: list = [
            ScriptRef(src=f"{base}/static/ux-channel.js", defer=True, id="ux-channel"),
        ]
        if bridge:
            refs.append(
                ScriptRef(src=f"{base}/static/ux-bridge.js", defer=True, id="ux-bridge")
            )
        if insp:
            refs.append(
                ScriptRef(
                    src=f"{base}/static/ux-inspector.js", defer=True, id="ux-inspector"
                )
            )
        rtc_on = webrtc
        if rtc_on is None:
            cfg = getattr(channel, "config", None)
            rtc_on = True if cfg is None else bool(getattr(cfg, "webrtc_enabled", True))
        if rtc_on:
            refs.append(
                ScriptRef(src=f"{base}/static/ux-webrtc.js", defer=True, id="ux-webrtc")
            )
        return Placement(
            attrs={},
            client={"endpoint": f"{base}/action", "path": base},
            scripts=tuple(refs),
            path=base,
            kind="runtime",
            meta={"dev": dev_b, "inspector": bool(insp)},
        )

    def body_attrs(
        *,
        endpoint: Optional[str] = None,
        dev: bool | None = None,
        inspector: bool | None = None,
        push_topic: Optional[str] = None,
        push_token: Optional[str] = None,
        push_ticket: Optional[str] = None,
        push: Optional[str] = None,
        ws: bool | str = False,
        webrtc: bool | str = False,
        webrtc_auto: bool = False,
        webrtc_media: bool | str = False,
        webrtc_ticket: str | None = None,
        extra: Optional[Mapping[str, str]] = None,
    ) -> dict[str, str]:
        """
        Attribute **dict** for your document body (Placement data, not HTML).

        Demo: ``ux_channel.render.kit.attr_string(ch.body_attrs(...))``.
        """
        dev_b, insp = _env_flags(dev, inspector)
        ep = endpoint or f"{channel.path.rstrip('/')}/action"
        attrs: dict[str, str] = {"data-channel-endpoint": ep}
        if dev_b:
            attrs["data-channel-dev"] = ""
        if insp:
            attrs["data-channel-inspector"] = ""
        if push_topic:
            attrs["data-channel-push-topic"] = str(push_topic)
        if push:
            attrs["data-channel-push"] = str(push)
        if push_token:
            attrs["data-channel-push-token"] = str(push_token)
        if push_ticket:
            attrs["data-channel-push-ticket"] = str(push_ticket)
        if ws:
            if ws is True:
                attrs["data-channel-ws"] = f"{channel.path.rstrip('/')}/ws"
            else:
                attrs["data-channel-ws"] = str(ws)
        if webrtc:
            cfg = getattr(channel, "config", None)
            rtc_on = True if cfg is None else bool(getattr(cfg, "webrtc_enabled", True))
            if rtc_on:
                attrs["data-channel-webrtc-rtc"] = f"{channel.path.rstrip('/')}/rtc"
                if webrtc is True:
                    attrs["data-channel-webrtc-room"] = "default"
                else:
                    attrs["data-channel-webrtc-room"] = str(webrtc)
                if webrtc_auto:
                    attrs["data-channel-webrtc-auto"] = ""
                if webrtc_media:
                    if webrtc_media is True:
                        attrs["data-channel-webrtc-media"] = "av"
                    else:
                        attrs["data-channel-webrtc-media"] = str(webrtc_media)
                try:
                    plane = getattr(channel, "webrtc", None)
                    if plane is not None:
                        attrs["data-channel-webrtc-ws"] = plane.ws_path
                        if webrtc_ticket:
                            attrs["data-channel-webrtc-ticket"] = str(webrtc_ticket)
                        ice = plane.default_ice_servers()
                        import json as _json

                        attrs["data-channel-webrtc-ice"] = _serde.dumps(
                            ice
                        )
                except Exception:
                    attrs.setdefault(
                        "data-channel-webrtc-ws",
                        f"{channel.path.rstrip('/')}/rtc/ws",
                    )
        if extra:
            attrs.update({str(k): str(v) for k, v in extra.items()})
        return attrs

    channel.runtime = runtime  # type: ignore[method-assign]
    channel.body_attrs = body_attrs  # type: ignore[method-assign]

    # Document HTML façade only — never region SSR ``ch.html``.
    for dead in (
        "document",
        "shell",
        "head",
        "scripts",
        "page",
        "body_attr_string",
        "button",
        "link",
        "submit",
        "form",
    ):
        if dead in getattr(channel, "__dict__", {}):
            try:
                delattr(channel, dead)
            except Exception:
                pass
