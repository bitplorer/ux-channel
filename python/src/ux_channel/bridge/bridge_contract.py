"""
Bridge contracts — how unknown npm APIs become knowable without FFI.

Problem
-------
Every package has different constructors, methods, and lifecycles.
Python cannot import Chart.js. Reflection across the wire is not FFI.

Resolution
----------
Each **adapter** (not the raw npm package) publishes a **contract**:

* lifecycle: mount / update / call / destroy (fixed shape for ux-bridge)
* methods: name → args schema (JSON-serializable)
* mount_props: JSON Schema-ish dict for props

Python loads the contract (file or register()) and validates **before**
emitting ops. JS adapter may also ``describe()`` for tooling.

Dynamic part: method *names* and *args* travel as JSON; shapes are checked
against the contract when present. Without a contract, calls are open
(warn-only) — adapter is last line of defense.
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional, Sequence

__all__ = [
    "MethodSpec",
    "BridgeContract",
    "ContractRegistry",
    "ValidationError",
    "load_contract",
    "contract_from_mapping",
]


class ValidationError(ValueError):
    """Contract validation failed (method or args)."""


@dataclass(frozen=True)
class MethodSpec:
    """One callable surface on the **adapter** (not every npm method)."""

    name: str
    args: tuple[dict[str, Any], ...] = ()  # [{name, type?, required?}]
    description: str = ""
    # If True, args may be a single object (kwargs-style) instead of list
    kwargs: bool = False

    def validate_args(self, args: Any) -> list[Any]:
        """Normalize to a JSON list for the wire; raise ValidationError."""
        if args is None:
            args = []
        # kwargs-style: dict → single-element or expand by schema names
        if isinstance(args, Mapping):
            if self.kwargs or (self.args and all("name" in a for a in self.args)):
                ordered = []
                for spec in self.args:
                    n = spec.get("name")
                    if n in args:
                        ordered.append(args[n])
                    elif spec.get("required", False):
                        raise ValidationError(
                            f"method {self.name!r} missing arg {n!r}"
                        )
                    else:
                        ordered.append(spec.get("default"))
                # include extras last if kwargs
                if self.kwargs:
                    known = {a.get("name") for a in self.args}
                    for k, v in args.items():
                        if k not in known:
                            ordered.append(v)
                return ordered
            # No arg schema: allow a single object payload (common npm pattern)
            if not self.args:
                return [dict(args)]
            raise ValidationError(
                f"method {self.name!r} expected list args or kwargs contract"
            )
        if not isinstance(args, (list, tuple)):
            raise ValidationError(
                f"method {self.name!r} args must be list or dict, got {type(args).__name__}"
            )
        args_l = list(args)
        required = [a for a in self.args if a.get("required")]
        if required and len(args_l) < len(required):
            raise ValidationError(
                f"method {self.name!r} needs ≥{len(required)} args, got {len(args_l)}"
            )
        if self.args and len(args_l) > len(self.args) and not self.kwargs:
            raise ValidationError(
                f"method {self.name!r} expects ≤{len(self.args)} args, got {len(args_l)}"
            )
        return args_l

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "args": list(self.args),
            "description": self.description,
            "kwargs": self.kwargs,
        }


@dataclass(frozen=True)
class BridgeContract:
    """
    Adapter contract — the anti-corruption layer for one npm package key.
    """

    package: str
    version: str = "0"
    schema_version: int = 1
    lifecycle: tuple[str, ...] = ("mount", "update", "call", "destroy")
    methods: Mapping[str, MethodSpec] = field(default_factory=dict)
    mount_props: Mapping[str, Any] = field(default_factory=dict)  # JSON Schema fragment
    events: tuple[str, ...] = ()
    description: str = ""
    npm: str = ""  # real npm package name e.g. chart.js

    def method_names(self) -> tuple[str, ...]:
        return tuple(self.methods.keys())

    def allows(self, method: str) -> bool:
        return method in self.methods

    def validate_call(self, method: str, args: Any = None) -> list[Any]:
        if method not in self.methods:
            raise ValidationError(
                f"method {method!r} not in contract for {self.package!r}; "
                f"known={list(self.methods)}"
            )
        return self.methods[method].validate_args(args)

    def validate_mount_props(self, props: Any) -> dict[str, Any]:
        """Light check: object type + required keys from mount_props.required."""
        if props is None:
            props = {}
        if not isinstance(props, Mapping):
            raise ValidationError("mount props must be a JSON object")
        props = dict(props)
        schema = self.mount_props or {}
        required = schema.get("required") or []
        for key in required:
            if key not in props:
                raise ValidationError(f"mount props missing required {key!r}")
        return props

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package": self.package,
            "version": self.version,
            "lifecycle": list(self.lifecycle),
            "methods": {k: v.as_dict() for k, v in self.methods.items()},
            "mount_props": dict(self.mount_props),
            "events": list(self.events),
            "description": self.description,
            "npm": self.npm,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return _serde.dumps(self.as_dict(), pretty=bool(indent))


def contract_from_mapping(data: Mapping[str, Any]) -> BridgeContract:
    methods_raw = data.get("methods") or {}
    methods: dict[str, MethodSpec] = {}
    if isinstance(methods_raw, Mapping):
        for name, spec in methods_raw.items():
            if isinstance(spec, MethodSpec):
                methods[str(name)] = spec
            elif isinstance(spec, Mapping):
                methods[str(name)] = MethodSpec(
                    name=str(spec.get("name") or name),
                    args=tuple(spec.get("args") or ()),
                    description=str(spec.get("description") or ""),
                    kwargs=bool(spec.get("kwargs")),
                )
            else:
                methods[str(name)] = MethodSpec(name=str(name))
    elif isinstance(methods_raw, (list, tuple)):
        for name in methods_raw:
            methods[str(name)] = MethodSpec(name=str(name))
    return BridgeContract(
        package=str(data["package"]),
        version=str(data.get("version") or "0"),
        schema_version=int(data.get("schema_version") or 1),
        lifecycle=tuple(data.get("lifecycle") or ("mount", "update", "call", "destroy")),
        methods=methods,
        mount_props=dict(data.get("mount_props") or {}),
        events=tuple(data.get("events") or ()),
        description=str(data.get("description") or ""),
        npm=str(data.get("npm") or ""),
    )


def load_contract(path: Path | str) -> BridgeContract:
    path = Path(path)
    data = _serde.loads(path.read_text(encoding="utf-8"))
    if "package" not in data:
        data = {**data, "package": path.stem}
    return contract_from_mapping(data)


class ContractRegistry:
    """In-process contracts keyed by package name."""

    def __init__(self) -> None:
        self._by_pkg: dict[str, BridgeContract] = {}

    def add(self, contract: BridgeContract) -> BridgeContract:
        self._by_pkg[contract.package] = contract
        return contract

    def get(self, package: str) -> Optional[BridgeContract]:
        return self._by_pkg.get(package)

    def packages(self) -> list[str]:
        return sorted(self._by_pkg)

    def validate_call(
        self, package: str, method: str, args: Any = None, *, strict: bool = True
    ) -> list[Any]:
        c = self.get(package)
        if c is None:
            if strict:
                raise ValidationError(
                    f"no contract for package {package!r}; "
                    f"ch.bridge.load_contract(...) or register(contract=...)"
                )
            if args is None:
                return []
            if isinstance(args, (list, tuple)):
                return list(args)
            if isinstance(args, Mapping):
                return [dict(args)]
            return [args]
        return c.validate_call(method, args)


# process default
_registry = ContractRegistry()


def get_contract_registry() -> ContractRegistry:
    return _registry


def set_contract_registry(reg: ContractRegistry) -> None:
    global _registry
    _registry = reg
