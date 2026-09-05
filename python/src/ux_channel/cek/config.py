"""ChannelConfig.cek parsing — off | adapt | require."""

from __future__ import annotations

from typing import Any

CEK_MODES = ("off", "adapt", "require")


def parse_cek(value: Any) -> str:
    """Normalize a cek mode. Unknown values fail closed.

    ``None`` means the cut #3 default: ``require`` (cek-runtime Host).
    Explicit ``False`` / ``"off"`` is the classic CapService escape.
    """
    if value is False:
        return "off"
    if value is None:
        return "require"
    if value is True:
        return "require"
    v = str(value).strip().lower()
    if v in ("0", "false", "no", "none"):
        return "off"
    if v in ("1", "true", "yes"):
        return "require"
    if v not in CEK_MODES:
        raise ValueError(
            f"ChannelConfig.cek must be one of {CEK_MODES}, got {value!r}. "
            "require = cek-runtime Host is the Cap machine (default); "
            "adapt = compare; off = classic CapService (explicit escape)."
        )
    return v


def cek_available() -> bool:
    """True when the optional extra ``[cek]`` wrap packages can be imported."""
    try:
        import cek_host  # noqa: F401
        import cek_surface  # noqa: F401
    except ImportError:
        return False
    return True


def min_cek() -> str:
    """Installed cek-host version, or empty if missing."""
    try:
        import cek_host

        return str(getattr(cek_host, "__version__", ""))
    except ImportError:
        return ""


def require_cek_installed(mode: str) -> None:
    """Fail closed when require/adapt is set but the extra is missing."""
    if mode == "off":
        return
    if cek_available():
        return
    raise RuntimeError(
        f"ChannelConfig.cek={mode!r} needs cek-host + cek-surface (>=0.1.3): "
        "pip install 'ux-channel[cek]'. "
        "Default decide is cek=require (cek-runtime Host). "
        "Bare-install escape: ChannelConfig(..., cek='off') or UX_CHANNEL_CEK=off. "
        "See Channel.help() / uxchannel recipe production."
    )
