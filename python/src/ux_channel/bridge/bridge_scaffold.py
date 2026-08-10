"""
Scaffold npm widget bridges — any package via string ops (not FFI).

Developer tooling::

    uxchannel bridge new chartjs --methods update,resetZoom
    uxchannel bridge explain
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ux_channel.devtools.errors import (
    DxConflictError,
    DxNotFoundError,
    DxUsageError,
    DxValidationError,
)
from ux_channel.devtools.log import get_log
from typing import Any, Iterable, Sequence

CONTRACT_SCHEMA_VERSION = 1
LIFECYCLE_OPS = ("mount", "update", "call", "destroy")

__all__ = [
    "slugify",
    "default_methods",
    "render_adapter_js",
    "render_package_json",
    "render_python_snippet",
    "render_readme",
    "render_contract_json",
    "create_bridge_package",
    "explain_bridge",
    "find_contract_path",
    "load_contract_file",
    "save_contract_file",
    "add_contract_method",
    "remove_contract_method",
    "list_contract_methods",
    "sync_register_py_methods",
    "normalize_contract",
    "CONTRACT_SCHEMA_VERSION",
]


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "widget"


def default_methods(extra: Sequence[str] | None = None) -> tuple[str, ...]:
    base = ["update", "destroy"]
    if extra:
        for m in extra:
            m = m.strip()
            if m and m not in base:
                base.append(m)
    return tuple(base)


def render_adapter_js(
    package: str,
    *,
    methods: Sequence[str],
    npm_import: str = "",
    global_name: str = "",
) -> str:
    """
    Universal adapter template.

    * Prefer ESM ``npm_import`` when bundling.
    * Or UMD ``global_name`` when loading from CDN.
    * Methods are string-dispatched in ``call``.
    """
    pkg = package
    methods = list(methods) or ["update", "destroy"]
    method_cases = "\n".join(
        f'      case "{m}":\n'
        f'        if (typeof handle.{m} === "function") return handle.{m}.apply(handle, args);\n'
        f'        break;'
        for m in methods
        if m not in ("destroy", "update")  # lifecycle separate
    )
    import_block = ""
    factory = "null"
    if npm_import:
        import_block = f'import Lib from "{npm_import}";\n'
        factory = "Lib"
    elif global_name:
        factory = f'(typeof globalThis !== "undefined" && globalThis.{global_name})'

    return f'''/**
 * uxchannel bridge adapter: {pkg}
 *
 * Register once in the browser (bundler entry or module script):
 *   import "./ux-bridge-{slugify(pkg)}.js"
 *
 * Python:
 *   ch.bridge.register("{pkg}", methods={list(methods)!r})
 *   ch.bridge.mount_spec("id", package="{pkg}", props={{...}})
 *   ch.bridge.mount_ops("id", "{pkg}", props={{...}})
 *   ch.bridge.call("id", "METHOD", package="{pkg}")
 *
 * Not FFI — string ops only. See docs/BRIDGE_CONTRACT.md
 */
{import_block}
function resolveLib() {{
  const Lib = {factory};
  if (!Lib) {{
    console.warn("[ux-bridge:{pkg}] library not found — set npm_import or load UMD");
  }}
  return Lib;
}}

function createAdapter() {{
  return {{
    /**
     * @param {{HTMLElement}} el host node
     * @param {{object}} props from bridge.mount / data-channel-bridge-props
     * @returns {{object|function}} handle (or destroy fn)
     */
    mount(el, props) {{
      const Lib = resolveLib();
      el.innerHTML = "";
      // Generic shell: canvas/root for the library
      const root = document.createElement("div");
      root.className = "ux-bridge-root";
      el.appendChild(root);
      if (!Lib) {{
        root.textContent = "[{pkg}] load library then remount";
        return {{ destroy() {{ el.innerHTML = ""; }} }};
      }}
      // --- customize: construct your library instance ---
      const handle =
        typeof Lib === "function"
          ? new Lib(root, props || {{}})
          : Lib.create
            ? Lib.create(root, props || {{}})
            : {{ el: root, props: props || {{}}, lib: Lib }};
      return handle;
    }},

    update(handle, props, replace) {{
      if (handle && typeof handle.update === "function") {{
        return handle.update(props, replace);
      }}
      if (handle) handle.props = replace ? props : Object.assign({{}}, handle.props || {{}}, props || {{}});
    }},

    call(handle, method, args) {{
      args = args || [];
      switch (method) {{
{method_cases}
        default: {{
          if (handle && typeof handle[method] === "function") {{
            return handle[method].apply(handle, args);
          }}
          console.warn("[ux-bridge:{pkg}] unknown method", method);
        }}
      }}
    }},

    destroy(handle) {{
      if (!handle) return;
      if (typeof handle === "function") return handle();
      if (typeof handle.destroy === "function") return handle.destroy();
      if (typeof handle.dispose === "function") return handle.dispose();
    }},
  }};
}}

function register() {{
  const api = typeof globalThis !== "undefined" ? globalThis.uxBridge : null;
  if (!api || typeof api.register !== "function") {{
    console.warn("[ux-bridge:{pkg}] uxBridge missing — load ux-bridge.js first");
    return;
  }}
  api.register("{pkg}", createAdapter());
}}

register();
export const packageName = "{pkg}";
export const methods = {json.dumps(list(methods))};

// Runtime describe for tooling (optional)
if (typeof globalThis !== "undefined" && globalThis.uxBridge) {{
  globalThis.uxBridge.contracts = globalThis.uxBridge.contracts || {{}};
  globalThis.uxBridge.contracts["{pkg}"] = {{
    package: "{pkg}",
    lifecycle: ["mount", "update", "call", "destroy"],
    methods: methods,
  }};
}}
'''


def render_package_json(package: str, *, npm_dep: str = "") -> str:
    name = f"@ux-channel/adapter-{slugify(package)}"
    deps = {}
    if npm_dep:
        deps[npm_dep.split("@")[0] if not npm_dep.startswith("@") else npm_dep] = "*"
        # better: npm_dep is "chart.js" or "chart.js@4"
        if "@" in npm_dep and not npm_dep.startswith("@"):
            n, _, ver = npm_dep.partition("@")
            deps = {n: ver or "*"}
        elif npm_dep.startswith("@") and npm_dep.count("@") >= 2:
            # @scope/pkg@ver
            parts = npm_dep.rsplit("@", 1)
            deps = {parts[0]: parts[1]}
        else:
            deps = {npm_dep: "*"}
    body = {
        "name": name,
        "version": "0.1.0",
        "description": f"uxchannel bridge adapter for {package}",
        "type": "module",
        "main": f"ux-bridge-{slugify(package)}.js",
        "files": [f"ux-bridge-{slugify(package)}.js", "README.md"],
        "peerDependencies": deps or {},
        "keywords": ["ux-channel", "bridge", package],
        "license": "MIT",
    }
    return json.dumps(body, indent=2) + "\n"


def render_python_snippet(package: str, methods: Sequence[str]) -> str:
    """register.py — factory façade + local METHODS (synced by add/remove-method)."""
    from ux_channel.bridge.bridge_preset_gen import class_name_for

    cls = class_name_for(package)
    methods_t = ", ".join(f'"{m}"' for m in sorted(methods))
    methods_tuple = f"({methods_t},)" if methods_t else "()"
    return (
        '"""Bridge preset entry (auto-generated).\n\n'
        "Application — callable factory façade::\n\n"
        f"    from .preset import {cls}\n\n"
        f"    widgets = {cls}(ch)\n"
        '    w = widgets("island-1", props={})\n'
        "    return w.commit(...)\n"
        "    # ux-dom: w.mount_spec().attrs\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        f'PACKAGE = "{package}"\n'
        f"METHODS = {methods_tuple}\n\n"
        "try:\n"
        f"    from .preset import {cls}, create\n"
        "except ImportError:  # pragma: no cover\n"
        f"    {cls} = None  # type: ignore\n"
        "    create = None  # type: ignore\n\n"
        f'__all__ = [{cls!r}, "PACKAGE", "METHODS", "create"]\n\n\n'
        "def register(ch) -> None:\n"
        '    ch.bridge.register(PACKAGE, methods=METHODS, description=f"preset:{PACKAGE}")\n'
    )



def render_contract_json(
    package: str,
    *,
    methods: Sequence[str],
    npm: str = "",
    mount_props: dict | None = None,
    method_specs: dict | None = None,
) -> str:
    """Contract JSON.

    * mount_props — npm mount/update fields → preset kwargs
    * method_specs — per-method args → contract + named preset methods
    """
    method_specs = method_specs or {}
    methods_obj = {}
    for m in methods:
        spec = method_specs.get(m) if isinstance(method_specs, dict) else None
        if isinstance(spec, dict):
            methods_obj[m] = _method_entry(
                m,
                args=spec.get("args") or (),
                kwargs=bool(spec.get("kwargs")),
                description=str(spec.get("description") or f"Adapter method {m}"),
            )
        else:
            methods_obj[m] = _method_entry(
                m, args=(), kwargs=False, description=f"Adapter method {m}"
            )
    if not isinstance(mount_props, dict) or not mount_props:
        mount_props = {
            "type": "object",
            "description": "Props for bridge.mount — declare properties for codegen",
            "properties": {},
            "required": [],
        }
    body = normalize_contract(
        {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "package": package,
            "version": "0.1.0",
            "npm": npm or package,
            "lifecycle": list(LIFECYCLE_OPS),
            "methods": methods_obj,
            "mount_props": mount_props,
            "events": [],
            "description": f"uxchannel adapter contract for {package}",
        }
    )
    return json.dumps(body, indent=2, sort_keys=False) + "\n"


def render_readme(package: str, methods: Sequence[str], npm_dep: str = "") -> str:
    from ux_channel.bridge.bridge_preset_gen import class_name_for

    cls = class_name_for(package)
    methods_list = "\n".join(f"- `{m}`" for m in methods)
    return f"""# Bridge preset: `{package}`

Callable **factory façade** (default codegen).

## Application Python

```python
from preset import {cls}          # or: from bridges.<mod> import {cls}

widgets = {cls}(ch)               # bind Channel.boot once
w = widgets("w1", props={{}})
return w.commit(...)              # Result + bridge ops
# ux-dom: w.mount_spec().attrs
```

## Browser

```js
// load ux-bridge.js from channel, then:
import "./ux-bridge-{slugify(package)}.js";
```

## Install npm dep

```bash
npm i {npm_dep or package}
```

## Methods

{methods_list}

Power escape: raw ``ch.bridge.*`` still works.
See uxchannel docs/BRIDGE_PRESETS.md and docs/BRIDGES_VS_UI_DOM.md.
"""



def create_bridge_package(
    dest: Path | str,
    package: str,
    *,
    methods: Sequence[str] | None = None,
    npm_dep: str = "",
    npm_import: str = "",
    global_name: str = "",
    force: bool = False,
    flat: bool = False,
    mount_props: dict | None = None,
    method_specs: dict | None = None,
) -> Path:
    """
    Write adapter package tree under *dest*.

    Returns the package directory path.
    """
    dest = Path(dest)
    pkg = package.strip()
    if not pkg:
        raise ValueError("package name required")
    methods = default_methods(methods)
    if flat:
        root = dest
    else:
        root = (
            dest
            if dest.name.startswith("adapter-") or (dest / "package.json").exists()
            else dest / f"adapter-{slugify(pkg)}"
        )
    if root.exists() and not force:
        if any(root.iterdir()):
            raise DxConflictError(
                f"adapter directory exists: {root}",
                code="bridge.adapter_exists",
                hint="pass --force to overwrite scaffold files",
                details={"path": str(root)},
            )
    root.mkdir(parents=True, exist_ok=True)

    js_name = f"ux-bridge-{slugify(pkg)}.js"
    (root / js_name).write_text(
        render_adapter_js(
            pkg,
            methods=methods,
            npm_import=npm_import or (npm_dep.split("@")[0] if npm_dep and not npm_dep.startswith("@") else npm_import),
            global_name=global_name,
        ),
        encoding="utf-8",
    )
    (root / "package.json").write_text(
        render_package_json(pkg, npm_dep=npm_dep or ""),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        render_readme(pkg, methods, npm_dep=npm_dep),
        encoding="utf-8",
    )
    (root / "register.py").write_text(
        render_python_snippet(pkg, methods),
        encoding="utf-8",
    )
    (root / "contract.json").write_text(
        render_contract_json(
            pkg,
            methods=methods,
            npm=npm_dep or "",
            mount_props=mount_props,
            method_specs=method_specs,
        ),
        encoding="utf-8",
    )
    log = get_log()
    log.ok("wrote bridge adapter package", path=str(root), package=pkg)
    log.info("files", files="contract.json,register.py,package.json,adapter.js,README.md")
    return root





def find_contract_path(
    package: str,
    *,
    start: Path | str | None = None,
    explicit: Path | str | None = None,
) -> Path:
    """
    Resolve contract.json for *package*.

    Search order: explicit path → start/contract.json → start/adapter-*/contract.json
    → recursive under start for matching package field.
    """
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise DxNotFoundError(
                f"contract not found: {path}",
                code="bridge.contract_not_found",
                hint="pass --contract PATH or: uxchannel bridge new <package>",
            )
        return path
    root = Path(start or ".")
    candidates = [
        root / "contract.json",
        root / f"adapter-{slugify(package)}" / "contract.json",
        root / "bridges" / f"adapter-{slugify(package)}" / "contract.json",
        root / "packages" / "@ux-channel" / f"adapter-{slugify(package)}" / "contract.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    if root.is_dir():
        for c in root.rglob("contract.json"):
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(data.get("package", "")).strip() == package.strip():
                return c
    raise DxNotFoundError(
        f"no contract.json for package {package!r} under {root}",
        code="bridge.contract_not_found",
        hint=f"uxchannel bridge new {package} --out {root}  OR  --contract PATH",
        details={"package": package, "search_root": str(root)},
    )


def _method_entry(
    name: str,
    *,
    args: Sequence[dict] | Sequence[str] = (),
    kwargs: bool = False,
    description: str = "",
) -> dict[str, Any]:
    """Canonical method object (stable keys, no extras)."""
    arg_list: list[dict[str, Any]] = []
    for a in args:
        if isinstance(a, str):
            arg_list.append(_parse_arg_token(a))
        elif isinstance(a, dict):
            ent: dict[str, Any] = {"name": str(a["name"])}
            if a.get("type"):
                ent["type"] = str(a["type"])
            if "required" in a:
                ent["required"] = bool(a["required"])
            if "default" in a:
                ent["default"] = a["default"]
            arg_list.append(ent)
        else:
            raise ValueError(f"invalid arg spec: {a!r}")
    return {
        "name": name,
        "args": arg_list,
        "description": description or f"Adapter method {name}",
        "kwargs": bool(kwargs),
    }


def _method_fingerprint(spec: dict) -> str:
    """Stable compare for idempotent add-method."""
    # only fields that affect wire validation
    slim = {
        "name": spec.get("name"),
        "args": spec.get("args") or [],
        "kwargs": bool(spec.get("kwargs")),
        # description intentionally excluded from equality of "behavior"
        # but included for full idempotency when user re-adds same desc
        "description": spec.get("description") or "",
    }
    return json.dumps(slim, sort_keys=True, separators=(",", ":"))


def normalize_contract(data: dict) -> dict[str, Any]:
    """
    Canonical contract shape for long-term stability.

    * schema_version
    * package, version, npm
    * lifecycle (fixed ops)
    * methods: map name → {name, args, description, kwargs}
    * mount_props, events, description
    """
    if not isinstance(data, dict):
        raise ValueError("contract must be a JSON object")
    pkg = str(data.get("package") or "").strip()
    if not pkg:
        raise ValueError("contract.package is required")

    methods_raw = data.get("methods") or {}
    methods: dict[str, Any] = {}
    if isinstance(methods_raw, list):
        for m in methods_raw:
            name = str(m).strip()
            if name:
                methods[name] = _method_entry(name)
    elif isinstance(methods_raw, dict):
        for key, spec in methods_raw.items():
            name = str(key).strip()
            if not name:
                continue
            if isinstance(spec, str):
                methods[name] = _method_entry(name, description=spec)
            elif isinstance(spec, dict):
                mname = str(spec.get("name") or name).strip()
                methods[mname] = _method_entry(
                    mname,
                    args=spec.get("args") or (),
                    kwargs=bool(spec.get("kwargs")),
                    description=str(spec.get("description") or ""),
                )
            else:
                methods[name] = _method_entry(name)
    else:
        raise ValueError("contract.methods must be object or list")

    # stable method key order
    methods = {k: methods[k] for k in sorted(methods)}

    lifecycle = data.get("lifecycle") or list(LIFECYCLE_OPS)
    if list(lifecycle) != list(LIFECYCLE_OPS):
        # coerce unknown lifecycles back to fixed set (ux-bridge only supports these)
        lifecycle = list(LIFECYCLE_OPS)

    mount_props = data.get("mount_props")
    if not isinstance(mount_props, dict):
        mount_props = {
            "type": "object",
            "description": "Props for bridge.mount",
            "required": [],
        }
    else:
        mount_props = dict(mount_props)
        mount_props.setdefault("type", "object")
        if "required" in mount_props and not isinstance(mount_props["required"], list):
            mount_props["required"] = list(mount_props["required"])

    events = data.get("events") or []
    if isinstance(events, str):
        events = [events]
    events = sorted({str(e) for e in events if e})

    out: dict[str, Any] = {
        "schema_version": int(data.get("schema_version") or CONTRACT_SCHEMA_VERSION),
        "package": pkg,
        "version": str(data.get("version") or "0.1.0"),
        "npm": str(data.get("npm") or pkg),
        "lifecycle": list(lifecycle),
        "methods": methods,
        "mount_props": mount_props,
        "events": events,
        "description": str(data.get("description") or f"uxchannel adapter contract for {pkg}"),
    }
    return out


def load_contract_file(path: Path | str) -> dict:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    return normalize_contract(data)


def save_contract_file(path: Path | str, data: dict) -> Path:
    path = Path(path)
    body = normalize_contract(data)
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path


def _parse_arg_token(token: str) -> dict:
    """
    Parse CLI --arg tokens:

    * name
    * name:type
    * name:type:required
    * name:type:optional
    """
    parts = [p.strip() for p in token.split(":")]
    if not parts or not parts[0]:
        raise DxValidationError(
            f"invalid --arg {token!r}",
            code="bridge.invalid_arg",
            hint="format: name | name:type | name:type:required",
        )
    # arg names: allow JS-ish identifiers
    name = parts[0]
    if not name.isidentifier():
        raise DxValidationError(
            f"invalid arg name {name!r}",
            code="bridge.invalid_arg_name",
            hint="arg names must be identifiers",
        )
    spec: dict = {"name": name}
    if len(parts) >= 2 and parts[1]:
        spec["type"] = parts[1]
    if len(parts) >= 3:
        flag = parts[2].lower()
        if flag in ("1", "true", "required", "req"):
            spec["required"] = True
        elif flag in ("0", "false", "optional", "opt"):
            spec["required"] = False
        else:
            raise DxValidationError(
                f"invalid --arg flag {parts[2]!r}; use required|optional",
                code="bridge.invalid_arg_flag",
            )
    return spec


def _validate_method_name(method: str) -> str:
    method = (method or "").strip()
    if not method or not method.isidentifier():
        raise DxValidationError(
            f"invalid method name {method!r}; use a JS identifier (e.g. resetZoom)",
            code="bridge.invalid_method_name",
            hint="examples: resetZoom, setData, flyTo",
        )
    return method


def add_contract_method(
    package: str,
    method: str,
    *,
    contract_path: Path | str | None = None,
    start: Path | str | None = None,
    args: Sequence[str] | None = None,
    kwargs: bool = False,
    description: str = "",
    sync_register: bool = True,
    force: bool = False,
) -> dict:
    """
    Add a method to contract.json — **idempotent**.

    * same name + same signature → action ``unchanged`` (no semantic change)
    * same name + different signature → ``updated`` if force else ValueError
    * new name → ``added``

    Dict keyed by method name prevents duplicates by construction.
    """
    method = _validate_method_name(method)
    path = find_contract_path(package, start=start, explicit=contract_path)
    data = load_contract_file(path)
    # ensure package field matches intent
    if data.get("package") and str(data["package"]) != package.strip():
        # still edit this file if user passed explicit path / search hit
        pass

    arg_specs = [_parse_arg_token(a) for a in (args or ())]
    # default description: keep existing on pure re-add without --desc
    existing = data["methods"].get(method)
    if description:
        desc = description
    elif existing and isinstance(existing, dict):
        desc = str(existing.get("description") or f"Adapter method {method}")
    else:
        desc = f"Adapter method {method}"

    new_spec = _method_entry(
        method, args=arg_specs, kwargs=kwargs, description=desc
    )

    if existing is not None:
        # compare behavior + description for full idempotency
        old_fp = _method_fingerprint(existing if isinstance(existing, dict) else _method_entry(method))
        new_fp = _method_fingerprint(new_spec)
        if old_fp == new_fp:
            # still normalize file once for schema stability (cheap)
            save_contract_file(path, data)
            if sync_register:
                sync_register_py_methods(path.parent, list(data["methods"]))
            log = get_log()
            log.info("method already present with same signature", method=method)
            log.ok("unchanged (idempotent)", method=method, path=str(path))
            return {
                "path": str(path),
                "package": data.get("package") or package,
                "method": method,
                "methods": sorted(data["methods"]),
                "action": "unchanged",
                "idempotent": True,
            }
        if not force:
            raise DxConflictError(
                f"method {method!r} already exists with a different signature",
                code="bridge.method_conflict",
                hint="re-run with --force to update, or: uxchannel bridge remove-method …",
                details={"existing": existing, "method": method},
            )
        action = "updated"
    else:
        action = "added"

    data["methods"][method] = new_spec
    save_contract_file(path, data)
    log = get_log()
    if sync_register:
        reg = path.parent / "register.py"
        if reg.is_file():
            sync_register_py_methods(path.parent, list(data["methods"]))
            log.debug("synced register.py methods list", path=str(reg))
        else:
            log.warn("register.py not found; skipped methods sync", dir=str(path.parent))
    log.ok(f"{action} method", method=method, path=str(path))
    log.info("methods now", methods=",".join(sorted(data["methods"])))
    return {
        "path": str(path),
        "package": data.get("package") or package,
        "method": method,
        "methods": sorted(data["methods"]),
        "action": action,
        "idempotent": action == "unchanged",
    }


def remove_contract_method(
    package: str,
    method: str,
    *,
    contract_path: Path | str | None = None,
    start: Path | str | None = None,
    sync_register: bool = True,
    missing_ok: bool = True,
) -> dict:
    """
    Remove a method — **idempotent** when missing_ok=True (default).

    * present → removed
    * absent → action ``absent`` (no error)
    """
    method = _validate_method_name(method)
    path = find_contract_path(package, start=start, explicit=contract_path)
    data = load_contract_file(path)
    if method not in data["methods"]:
        if not missing_ok:
            raise KeyError(
                f"method {method!r} not in {path}; known={sorted(data['methods'])}"
            )
        log = get_log()
        log.info("method already absent", method=method)
        log.ok("absent (idempotent)", method=method, path=str(path))
        return {
            "path": str(path),
            "package": data.get("package") or package,
            "method": method,
            "methods": sorted(data["methods"]),
            "action": "absent",
            "idempotent": True,
        }
    del data["methods"][method]
    save_contract_file(path, data)
    log = get_log()
    if sync_register:
        reg = path.parent / "register.py"
        if reg.is_file():
            sync_register_py_methods(path.parent, list(data["methods"]))
            log.debug("synced register.py methods list", path=str(reg))
        else:
            log.warn("register.py not found; skipped methods sync", dir=str(path.parent))
    log.ok("removed method", method=method, path=str(path))
    log.info("methods now", methods=",".join(sorted(data["methods"])) or "(none)")
    return {
        "path": str(path),
        "package": data.get("package") or package,
        "method": method,
        "methods": sorted(data["methods"]),
        "action": "removed",
        "idempotent": False,
    }


def list_contract_methods(
    package: str,
    *,
    contract_path: Path | str | None = None,
    start: Path | str | None = None,
) -> dict:
    path = find_contract_path(package, start=start, explicit=contract_path)
    data = load_contract_file(path)
    methods = data.get("methods") or {}
    detail = []
    for name, spec in sorted(methods.items()):
        if isinstance(spec, dict):
            detail.append(
                {
                    "name": name,
                    "args": spec.get("args") or [],
                    "kwargs": bool(spec.get("kwargs")),
                    "description": spec.get("description") or "",
                }
            )
        else:
            detail.append(
                {"name": name, "args": [], "kwargs": False, "description": ""}
            )
    return {
        "path": str(path),
        "package": data.get("package") or package,
        "schema_version": data.get("schema_version"),
        "lifecycle": data.get("lifecycle"),
        "events": data.get("events") or [],
        "npm": data.get("npm"),
        "methods": detail,
        "names": [d["name"] for d in detail],
    }


def sync_register_py_methods(adapter_dir: Path | str, methods: Sequence[str]) -> None:
    """
    Keep Python façade allowlists in sync with contract methods.

    Updates (best-effort):
    * register.py — METHODS = (...) or methods=(...)
    * preset.py — METHODS = (...)
    * PRESET.json — methods list
    """
    import re as _re

    root = Path(adapter_dir)
    methods_sorted = tuple(sorted(str(m) for m in methods if m))
    methods_t = ", ".join(f'"{m}"' for m in methods_sorted)
    methods_tuple_src = f"({methods_t},)" if methods_t else "()"

    def _patch_file(path: Path) -> bool:
        if not path.is_file():
            return False
        text = path.read_text(encoding="utf-8")
        original = text
        # METHODS = ("a", "b",)
        text, n1 = _re.subn(
            r"METHODS\s*=\s*\([^)]*\)",
            f"METHODS = {methods_tuple_src}",
            text,
            count=1,
        )
        # ch.bridge.register(..., methods=(...), ...)
        text, n2 = _re.subn(
            r"methods=\([^)]*\)",
            f"methods={methods_tuple_src}",
            text,
            count=1,
        )
        if text != original:
            path.write_text(text, encoding="utf-8")
            return True
        return bool(n1 or n2)

    _patch_file(root / "register.py")
    _patch_file(root / "preset.py")
    meta = root / "PRESET.json"
    if meta.is_file():
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            data["methods"] = list(methods_sorted)
            meta.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass


def explain_bridge() -> str:
    return """uxchannel bridge — any npm package (not FFI)

  Browser:  uxBridge.register(package, { mount, update, call, destroy })
  Python:   ch.bridge.*  OR auto preset.preset.ClassBridge
  Wire:     JSON ops bridge.mount|update|call|destroy

Commands:
  uxchannel bridge catalog
  uxchannel bridge preset <name|npm> [--methods a,b] [--npm …] [--out bridges]
  uxchannel bridge new <package>     # thin adapter only
  uxchannel bridge methods|add-method|remove-method
  uxchannel bridge recipe

Scaffold with presets:
  uxchannel create-app myapp --bridge chartjs --bridge leaflet

Catalog: chartjs, leaflet, codemirror — or any npm package name.

Docs: docs/BRIDGE_CONTRACT.md  docs/BRIDGES_VS_UI_DOM.md
"""
