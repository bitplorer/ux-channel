"""ux-dom may be a Poetry optional extra. It must not be a hard dependency."""

from __future__ import annotations

import pytest


def parse_poetry_deps(text: str) -> dict[str, str]:
    """Tiny extractor for ``[tool.poetry.dependencies]`` — no toml dependency."""
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


def spec_is_optional(spec: str) -> bool:
    """True when a Poetry dep table sets ``optional = true``."""
    compact = "".join(spec.split()).strip("{}")
    return any(part == "optional=true" for part in compact.split(","))


def assert_ux_dom_is_not_a_hard_dep(text: str) -> None:
    deps = parse_poetry_deps(text)
    hard = [
        name
        for name in ("ux-dom", "ux_dom")
        if name in deps and not spec_is_optional(deps[name])
    ]
    assert hard == []


def assert_hard_ux_dom_deps_fail() -> None:
    """Required ux-dom lines fail the gate. The same pin with optional = true passes."""
    header = "[tool.poetry.dependencies]\n"
    pin = (
        'ux-dom = { git = "https://github.com/bitplorer/ux-dom.git", '
        'rev = "19af869ecbb108f3cf779111838e3359b33a8131"'
    )
    required_shapes = (
        header + pin + " }\n",
        header + 'ux-dom = ">=0.1"\n',
        header + 'ux_dom = { version = ">=0.1" }\n',
        header + 'ux-dom = { version = ">=0.1", optional = false }\n',
    )
    for sample in required_shapes:
        with pytest.raises(AssertionError):
            assert_ux_dom_is_not_a_hard_dep(sample)
    assert_ux_dom_is_not_a_hard_dep(header + pin + ", optional = true }\n")
    assert_ux_dom_is_not_a_hard_dep('[tool.poetry.extras]\nux-dom = ["ux-dom"]\n')
