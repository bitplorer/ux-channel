"""Bind Channel's Cap façade to the cek-runtime Host path (cut #3).

Kernel SSoT is cek-runtime (ADR 0008). This module is a wrap, not a second
kernel and not a new pyo3 extension.

ONE mint / verify owner
    ``cek_host.Host`` — documented language port of decide. Stateful mint /
    verify / once / sealed-args. ``host-json`` is a fresh Host per call, so
    Channel tokens stay on this port. ``RustHostKernel`` / ``CEK_BIN`` is
    reachability of the runtime binary, not a second mint path.

``cek-host``'s console script is **not** the runtime binary (it has no
``host-json``). Probe before claiming rust_wrap reachability.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

log = logging.getLogger("ux_channel.cek.runtime_host")

KERNEL_SSOT = "cek-runtime"
KERNEL_SSOT_ADR = "0008"

# cek-host 0.1.3 Host / CapService has no HMAC previous_secrets API.
# Channel must not silently drop a rotation window on cek=require (cut #5D).
PREVIOUS_SECRETS_REQUIRE_MSG = (
    "previous_secrets is not wired on cek=require "
    "(cek-runtime Host has no HMAC previous_secrets API). "
    "Unset previous_secrets / UX_CHANNEL_PREVIOUS_SECRETS, or pin cek='off' "
    "for classic CapService rotation."
)


def previous_secrets_nonempty(previous_secrets: Optional[Sequence[str]] = None) -> bool:
    return any(str(s).strip() for s in (previous_secrets or ()) if s is not None)


def refuse_previous_secrets_on_require(
    previous_secrets: Optional[Sequence[str]] = None,
    *,
    mode: str = "require",
) -> None:
    """Loud fail when a rotation window is asked of Host (no second Cap machine)."""
    if mode != "require":
        return
    if previous_secrets_nonempty(previous_secrets):
        raise RuntimeError(PREVIOUS_SECRETS_REQUIRE_MSG)


def diagnose_previous_secrets(config: Any = None, registry: Any = None) -> dict[str, Any]:
    """Honest rotation snapshot (no secrets). Host does not verify previous_secrets."""
    from ux_channel.cek.config import parse_cek

    prev = tuple(getattr(config, "previous_secrets", ()) or ()) if config is not None else ()
    configured = previous_secrets_nonempty(prev)
    cek = parse_cek(getattr(config, "cek", "require") if config is not None else "require")
    caps = getattr(registry, "_caps", None) if registry is not None else None
    host_owned = type(caps).__name__ == "CekHostCapService" if caps is not None else cek == "require"
    if cek == "require" or host_owned:
        return {
            "configured": configured,
            "wired": False,
            "verify": "unwired",
            "note": (
                "cek=require Host has no HMAC previous_secrets API; "
                "rotation is classic CapService (cek=off) only"
            ),
        }
    classic_prev = bool(getattr(caps, "_previous", ()) or ()) if caps is not None else configured
    return {
        "configured": configured or classic_prev,
        "wired": classic_prev,
        "verify": "classic CapService" if (classic_prev or configured) else "none",
        "note": "previous_secrets rotate on classic CapService (cek=off)",
    }


def is_runtime_cek_bin(path: str | os.PathLike[str] | None) -> bool:
    """True when ``path`` is cek-runtime ``cek`` (supports ``host-json``)."""
    if not path:
        return False
    p = Path(path)
    if not p.is_file():
        return False
    try:
        proc = subprocess.run(
            [str(p)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False
    text = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    if "cek_host" in text or "cek_host.cli" in text:
        return False
    return "host-json" in text


def find_runtime_cek_bin() -> Optional[str]:
    """CEK_BIN or a probed ``cek`` that actually wraps cek-host-kernel."""
    env = os.environ.get("CEK_BIN")
    if env and is_runtime_cek_bin(env):
        return env
    try:
        from cek_host.rust_wrap import find_cek_bin
    except ImportError:
        find_cek_bin = None  # type: ignore[assignment]
    candidates: list[str] = []
    if find_cek_bin is not None:
        found = find_cek_bin()
        if found:
            candidates.append(found)
    which = _which_cek()
    if which:
        candidates.append(which)
    here = Path(__file__).resolve()
    for root in (
        Path("/tmp/cek-src/cek-runtime"),
        Path("/workspace/cek-runtime"),
        here.parents[5] / "cek-runtime" if len(here.parents) > 5 else None,
    ):
        if root is None:
            continue
        for kind in ("release", "debug"):
            cand = root / "target" / kind / "cek"
            candidates.append(str(cand))
    seen: set[str] = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        if is_runtime_cek_bin(c):
            return c
    return None


def _which_cek() -> Optional[str]:
    import shutil

    w = shutil.which("cek")
    return w


def runtime_wrap_available() -> bool:
    return find_runtime_cek_bin() is not None


@dataclass
class RuntimeHostBind:
    """cek-runtime Host wrap bound for Channel's Cap façade.

    ``host`` is the only mint / verify owner. ``runtime_kernel`` is always
    None — CEK_BIN rust_wrap is not a second Cap machine (ADR 0010).
    """

    kernel_ssot: str
    kernel_ssot_adr: str
    backend: str  # rust_wrap | port_host  (reachability; mint owner is host)
    host: Any
    runtime_kernel: Any | None
    bin_path: str | None


def bind_runtime_host(
    secret: str,
    *,
    max_age: int = 3600,
    previous_secrets: Optional[Sequence[str]] = None,
) -> RuntimeHostBind:
    """Open the one mint/verify owner: documented port Host.

    When ``CEK_BIN`` is a real cek-runtime binary, ``backend`` is
    ``rust_wrap`` (kernel reachability). That binary is not bound as a
    second mint path — host-json is a fresh Host per call.

    ``previous_secrets`` is not a Host API today. Non-empty on this path
    is a hard refuse (cut #5D) — never a silent ``_ = previous_secrets``.
    """
    refuse_previous_secrets_on_require(previous_secrets, mode="require")
    from cek_host import Host, MemoryOnceBackend

    raw = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
    port = Host(
        secret=raw,
        ttl_s=int(max_age or 3600),
        once=MemoryOnceBackend(),
        require_cap=True,
    )
    bin_path = find_runtime_cek_bin()
    backend = "rust_wrap" if bin_path else "port_host"
    if bin_path:
        log.info(
            "cek-runtime Host wrap: port Host is the mint/verify owner; "
            "CEK_BIN=%s reachable (ADR %s)",
            bin_path,
            KERNEL_SSOT_ADR,
        )
    else:
        log.info(
            "cek-runtime Host wrap: documented port Host (cek_host.Host); "
            "set CEK_BIN to cek-runtime `cek` for rust_wrap reachability (ADR %s)",
            KERNEL_SSOT_ADR,
        )
    return RuntimeHostBind(
        kernel_ssot=KERNEL_SSOT,
        kernel_ssot_adr=KERNEL_SSOT_ADR,
        backend=backend,
        host=port,
        runtime_kernel=None,
        bin_path=bin_path,
    )
