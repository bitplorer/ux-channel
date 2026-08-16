"""ChannelConfig.cek parsing — off | adapt | require."""

from __future__ import annotations

from typing import Any

CEK_MODES = ("off", "adapt", "require")


def parse_cek(value: Any) -> str:
    """Normalize a cek mode. Unknown values fail closed."""
    if value is None or value is False:
        return "off"
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
            "off = today's path; adapt = compare; require = cek-host.Host is the Cap machine."
        )
    return v


def cek_available() -> bool:
    """True when the optional extra ``[cek]`` can be imported."""
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
        f"ChannelConfig.cek={mode!r} needs the optional extra: "
        "pip install 'ux-channel[cek]'. "
        "Default remains cek=off (today's path, zero new imports). "
        "See Channel.help() / uxchannel recipe production."
    )
