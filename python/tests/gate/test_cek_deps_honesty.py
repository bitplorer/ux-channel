"""Lock pyproject: wrap packages are required; [cek] extra is an empty alias."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = ROOT / "python" / "pyproject.toml"


def _parse_simple_toml_deps(text: str) -> dict[str, str]:
    """Tiny extractor — avoids adding a toml dependency to the gate."""
    deps: dict[str, str] = {}
    in_deps = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_deps = line == "[tool.poetry.dependencies]"
            continue
        if not in_deps or "=" not in line or line.startswith("#"):
            continue
        name, _, rest = line.partition("=")
        deps[name.strip()] = rest.strip()
    return deps


def _parse_extras(text: str) -> dict[str, str]:
    extras: dict[str, str] = {}
    in_extras = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_extras = line == "[tool.poetry.extras]"
            continue
        if not in_extras or "=" not in line or line.startswith("#"):
            continue
        name, _, rest = line.partition("=")
        extras[name.strip()] = rest.strip()
    return extras


def test_cek_wrap_packages_are_required_deps():
    text = PYPROJECT.read_text(encoding="utf-8")
    deps = _parse_simple_toml_deps(text)
    assert "cek-host" in deps, deps.keys()
    assert "cek-surface" in deps, deps.keys()
    assert "0.1.3" in deps["cek-host"]
    assert "0.1.3" in deps["cek-surface"]


def test_cek_extra_is_empty_alias():
    text = PYPROJECT.read_text(encoding="utf-8")
    extras = _parse_extras(text)
    assert extras.get("cek") == "[]"


def test_require_cek_installed_names_packages_not_empty_extra():
    from ux_channel.cek.config import require_cek_installed

    require_cek_installed("require")
    src = (ROOT / "python/src/ux_channel/cek/config.py").read_text(encoding="utf-8")
    assert "pip install 'ux-channel[cek]'" not in src
    assert "cek-host" in src and "cek-surface" in src
    assert "empty alias" in src
