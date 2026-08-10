"""
Automate bridge **preset** creation (adapter + contract + Python façade).

CLI::

    uxchannel bridge catalog
    uxchannel bridge preset chartjs
    uxchannel bridge preset my-lib --methods foo,bar --npm my-lib

Scaffold::

    uxchannel create-app myapp --bridge chartjs
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from ux_channel.bridge.bridge_scaffold import (
    create_bridge_package,
    default_methods,
    slugify,
)
from ux_channel.devtools.errors import DxConflictError, DxUsageError
from ux_channel.devtools.log import get_log

__all__ = [
    "KNOWN_PRESETS",
    "list_known_presets",
    "resolve_preset_spec",
    "create_bridge_preset",
    "render_preset_py",
    "class_name_for",
    "module_name_for",
    "write_bridges_index",
]

KNOWN_PRESETS: dict[str, dict[str, Any]] = {
    "chartjs": {
        "package": "chart.js",
        "npm": "chart.js",
        "import": "chart.js",
        "global": "Chart",
        "methods": ("update", "destroy", "setType", "setData"),
        "method_specs": {
            "update": {"args": [], "description": "Chart.update()"},
            "destroy": {"args": [], "description": "Chart.destroy()"},
            "setType": {
                "args": [{"name": "type", "type": "string", "required": True}],
                "description": "Change chart type",
            },
            "setData": {
                "args": [{"name": "data", "type": "object", "required": True}],
                "description": "Replace chart data",
            },
        },
        "kind": "chart",
        "description": "Chart.js 4",
        "use_builtin": "ux_channel.bridges.ChartBridge",
        "mount_props": {
            "type": "object",
            "description": "Chart.js config fragment passed as bridge props",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "bar | line | doughnut | pie | …",
                },
                "data": {
                    "type": "object",
                    "description": "Chart.js data { labels, datasets }",
                },
                "labels": {"type": "array", "description": "Shortcut → data.labels"},
                "datasets": {"type": "array", "description": "Shortcut → data.datasets"},
                "options": {
                    "type": "object",
                    "description": "Chart.js options (plugins, scales, layout, …)",
                },
                "title": {"type": "string", "description": "Convenience title → options.plugins.title"},
            },
            "required": [],
        },
    },
    "chart.js": {
        "package": "chart.js",
        "npm": "chart.js",
        "import": "chart.js",
        "global": "Chart",
        "methods": ("update", "destroy", "setType", "setData"),
        "kind": "chart",
        "description": "Chart.js 4",
        "use_builtin": "ux_channel.bridges.ChartBridge",
        "mount_props": None,  # filled from chartjs key at resolve
    },

    "confetti": {
        "package": "ux-fx/confetti",
        "npm": "ux-fx",
        "methods": ("update", "destroy", "burst", "cannon", "rain", "stop"),
        "kind": "fx",
        "description": "Canvas confetti bursts",
        "use_builtin": "ux_channel.bridges.ConfettiBridge",
    },
    "particles": {
        "package": "ux-fx/particles",
        "npm": "ux-fx",
        "methods": ("update", "destroy", "pulse", "burst"),
        "kind": "fx",
        "description": "Ambient particle field",
        "use_builtin": "ux_channel.bridges.ParticlesBridge",
    },
    "aurora": {
        "package": "ux-fx/aurora",
        "npm": "ux-fx",
        "methods": ("update", "destroy", "pause", "play"),
        "kind": "fx",
        "description": "Animated aurora mesh gradient",
        "use_builtin": "ux_channel.bridges.AuroraBridge",
    },
    "countup": {
        "package": "ux-fx/countup",
        "npm": "ux-fx",
        "methods": ("update", "destroy", "setValue", "replay"),
        "kind": "fx",
        "description": "Animated metric count-up",
        "use_builtin": "ux_channel.bridges.CountUpBridge",
    },
    "spotlight": {
        "package": "ux-fx/spotlight",
        "npm": "ux-fx",
        "methods": ("update", "destroy"),
        "kind": "fx",
        "description": "Mouse spotlight glass glow",
        "use_builtin": "ux_channel.bridges.SpotlightBridge",
    },
    "lottie": {
        "package": "lottie-web",
        "npm": "lottie-web",
        "import": "lottie-web",
        "global": "lottie",
        "methods": ("update", "destroy", "play", "pause", "stop", "setSpeed", "goToAndPlay"),
        "kind": "fx",
        "description": "Lottie animations",
        "use_builtin": "ux_channel.bridges.LottieBridge",
    },

    "tom-select": {
        "package": "tom-select",
        "npm": "tom-select",
        "methods": ("update", "destroy", "setValue", "clear", "enable", "disable"),
        "kind": "form",
        "description": "Searchable select",
        "use_builtin": "ux_channel.bridges.SelectBridge",
    },
    "flatpickr": {
        "package": "flatpickr",
        "npm": "flatpickr",
        "methods": ("update", "destroy", "setDate", "clear", "open", "close"),
        "kind": "form",
        "description": "Date picker",
        "use_builtin": "ux_channel.bridges.DatePickerBridge",
    },
    "sortablejs": {
        "package": "sortablejs",
        "npm": "sortablejs",
        "methods": ("update", "destroy", "setOrder", "toArray"),
        "kind": "list",
        "description": "Drag-and-drop list",
        "use_builtin": "ux_channel.bridges.SortableBridge",
    },
    "swiper": {
        "package": "swiper",
        "npm": "swiper",
        "methods": ("update", "destroy", "slideTo", "slideNext", "slidePrev"),
        "kind": "media",
        "description": "Carousel",
        "use_builtin": "ux_channel.bridges.SwiperBridge",
    },
    "mermaid": {
        "package": "mermaid",
        "npm": "mermaid",
        "methods": ("update", "destroy", "render"),
        "kind": "diagram",
        "description": "Mermaid diagrams",
        "use_builtin": "ux_channel.bridges.MermaidBridge",
    },
    "quill": {
        "package": "quill",
        "npm": "quill",
        "methods": ("update", "destroy", "setContents", "setText", "enable"),
        "kind": "editor",
        "description": "Rich text editor",
        "use_builtin": "ux_channel.bridges.QuillBridge",
    },
    "leaflet": {
        "package": "leaflet",
        "npm": "leaflet",
        "import": "leaflet",
        "global": "L",
        "methods": ("setView", "flyTo", "invalidateSize", "destroy"),
        "method_specs": {
            "setView": {
                "args": [
                    {"name": "center", "type": "array", "required": True},
                    {"name": "zoom", "type": "number", "required": False},
                ],
                "description": "map.setView(center, zoom)",
            },
            "flyTo": {
                "args": [
                    {"name": "center", "type": "array", "required": True},
                    {"name": "zoom", "type": "number", "required": False},
                ],
                "description": "map.flyTo(center, zoom)",
            },
            "invalidateSize": {"args": [], "description": "map.invalidateSize()"},
            "destroy": {"args": [], "description": "remove map"},
        },
        "kind": "map",
        "description": "Leaflet map",
        "mount_props": {
            "type": "object",
            "properties": {
                "center": {"type": "array", "description": "[lat, lng]"},
                "zoom": {"type": "number"},
                "layers": {"type": "array"},
                "options": {"type": "object", "description": "L.map options"},
            },
        },
    },
    "codemirror": {
        "package": "codemirror",
        "npm": "codemirror",
        "import": "codemirror",
        "global": "CodeMirror",
        "methods": ("setValue", "getValue", "destroy"),
        "method_specs": {
            "setValue": {
                "args": [{"name": "value", "type": "string", "required": True}],
                "description": "Set editor document",
            },
            "getValue": {"args": [], "description": "Read editor document (client)"},
            "destroy": {"args": [], "description": "Teardown editor"},
        },
        "kind": "editor",
        "description": "CodeMirror editor",
        "mount_props": {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
                "language": {"type": "string"},
                "theme": {"type": "string", "description": "Editor theme id if package supports it"},
                "extensions": {"type": "array"},
            },
        },
    },
}


def list_known_presets() -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for key, meta in KNOWN_PRESETS.items():
        pkg = str(meta["package"])
        if pkg in seen:
            continue
        seen.add(pkg)
        out.append(
            {
                "key": key if key != "chart.js" else "chartjs",
                "package": pkg,
                "npm": meta.get("npm") or pkg,
                "methods": list(meta.get("methods") or ()),
                "kind": meta.get("kind") or "widget",
                "description": meta.get("description") or "",
                "builtin": meta.get("use_builtin") or "",
            }
        )
    return out


def resolve_preset_spec(
    name: str,
    *,
    methods: Sequence[str] | None = None,
    npm: str = "",
    npm_import: str = "",
    global_name: str = "",
) -> dict[str, Any]:
    key = (name or "").strip()
    if not key:
        raise DxUsageError(
            "preset name required",
            code="bridge.preset_name",
            hint="uxchannel bridge preset chartjs  OR  uxchannel bridge catalog",
        )
    low = key.lower()
    if low in KNOWN_PRESETS:
        meta = KNOWN_PRESETS[low]
        pkg = str(meta["package"])
        mp = meta.get("mount_props")
        if mp is None and low == "chart.js":
            mp = KNOWN_PRESETS["chartjs"].get("mount_props")
        return {
            "package": pkg,
            "npm": npm or str(meta.get("npm") or pkg),
            "npm_import": npm_import or str(meta.get("import") or ""),
            "global_name": global_name or str(meta.get("global") or ""),
            "methods": tuple(methods)
            if methods
            else tuple(meta.get("methods") or default_methods()),
            "kind": str(meta.get("kind") or "widget"),
            "description": str(meta.get("description") or ""),
            "use_builtin": str(meta.get("use_builtin") or ""),
            "catalog_key": low,
            "mount_props": mp if isinstance(mp, dict) else {},
            "method_specs": dict(meta.get("method_specs") or {}),
        }
    return {
        "package": key,
        "npm": npm or key,
        "npm_import": npm_import or "",
        "global_name": global_name or "",
        "methods": tuple(methods) if methods else default_methods(),
        "kind": "widget",
        "description": f"Generated bridge preset for {key}",
        "use_builtin": "",
        "catalog_key": "",
        "mount_props": {},
        "method_specs": {},
    }


def class_name_for(package: str) -> str:
    parts = [p for p in re.split(r"[^a-zA-Z0-9]+", package) if p]
    if not parts:
        return "GeneratedBridge"
    name = "".join(p[:1].upper() + p[1:] for p in parts)
    if not name.endswith("Bridge"):
        name += "Bridge"
    return name


def _mount_prop_names(mount_props: dict) -> list[str]:
    props = mount_props.get("properties") if isinstance(mount_props, dict) else None
    if not isinstance(props, dict):
        return []
    return [str(k) for k in props.keys()]


def _mount_prop_docs(mount_props: dict) -> list[str]:
    props = mount_props.get("properties") if isinstance(mount_props, dict) else None
    if not isinstance(props, dict):
        return []
    lines = []
    for name, schema in props.items():
        if isinstance(schema, dict):
            desc = schema.get("description") or schema.get("type") or ""
            lines.append(f"    * ``{name}`` — {desc}")
        else:
            lines.append(f"    * ``{name}``")
    return lines


def _py_method_name(js_name: str) -> str:
    """setView → set_view; avoid clobbering Python reserved façade methods."""
    import re

    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", js_name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()
    reserved = {
        "update",
        "call",
        "commit",
        "configure",
        "register",
        "props",
        "mount",
        "create",
        "describe",
    }
    if s in reserved:
        s = f"invoke_{s}"
    return s


def _render_named_methods(method_specs: dict, cls: str) -> list[str]:
    """Generate named methods from contract method_specs (args → params)."""
    lines: list[str] = []
    if not method_specs:
        return lines
    lines.append("    # --- package methods (from contract.json) ---")
    for js_name, spec in method_specs.items():
        if not isinstance(spec, dict):
            spec = {}
        args = [a for a in (spec.get("args") or []) if isinstance(a, dict)]
        py = _py_method_name(str(js_name))
        desc = str(spec.get("description") or js_name)

        # commit-style (Result)
        params = ["self"]
        for a in args:
            n = str(a.get("name") or "arg")
            if a.get("required", True):
                params.append(f"{n}: Any")
            else:
                params.append(f"{n}: Any = None")
        params.append("*, notice: str | None = None")
        lines.append(f"    def {py}({', '.join(params)}) -> Any:")
        lines.append(f'        """{desc} → bridge.call({js_name!r}) + Result."""')
        lines.append("        self._require_island()")
        lines.append("        call_args: list[Any] = []")
        for a in args:
            n = str(a.get("name") or "arg")
            if a.get("required", True):
                lines.append(f"        call_args.append({n})")
            else:
                lines.append(f"        if {n} is not None:")
                lines.append(f"            call_args.append({n})")
        lines.append(
            f'        return self._result_with_ops(self.call("{js_name}", *call_args), notice=notice)'
        )
        lines.append("")

        # ops-only
        op_params = ["self"]
        for a in args:
            n = str(a.get("name") or "arg")
            if a.get("required", True):
                op_params.append(f"{n}: Any")
            else:
                op_params.append(f"{n}: Any = None")
        lines.append(f"    def {py}_ops({', '.join(op_params)}) -> list:")
        lines.append(f'        """{desc} → bridge.call ops only."""')
        lines.append("        self._require_island()")
        lines.append("        call_args: list[Any] = []")
        for a in args:
            n = str(a.get("name") or "arg")
            if a.get("required", True):
                lines.append(f"        call_args.append({n})")
            else:
                lines.append(f"        if {n} is not None:")
                lines.append(f"            call_args.append({n})")
        lines.append(f'        return self.call("{js_name}", *call_args)')
        lines.append("")
    return lines



def render_preset_py(spec: dict[str, Any]) -> str:
    """Codegen: factory façade + props **from contract mount_props only**."""
    pkg = spec["package"]
    methods = list(spec["methods"])
    cls = class_name_for(pkg)
    methods_t = ", ".join(f'"{m}"' for m in methods)
    builtin = spec.get("use_builtin") or ""
    _mp = spec.get("mount_props")
    mount_props: dict = _mp if isinstance(_mp, dict) else {}
    prop_names = _mount_prop_names(mount_props)
    prop_docs = _mount_prop_docs(mount_props)
    prop_tuple = ", ".join(f'"{n}"' for n in prop_names)
    prop_doc_block = "\n".join(prop_docs) if prop_docs else "    * (declare properties in contract.json mount_props)"

    lines = [
        f'"""Auto-generated bridge preset for ``{pkg}``.',
        "",
        "Produced by: ``uxchannel bridge preset``",
        "",
        "Application — callable factory (props = npm package fields from contract)::",
        "",
        f"    widgets = {cls}(ch)",
        f"    w = widgets('island-id', ...package props...)",
        "    return w.commit(...)",
        "    # ux-dom host: w.mount_spec().attrs  (you style the element in ux-dom)",
        "",
        "Mount props (from contract.json — only what this package declares):",
        prop_doc_block,
        "",
        "* Data plane only. No invented css= — if the package has a style field,",
        "  it appears above because it is in mount_props.",
        "* Markup / CSS classes: ux-dom on the host element.",
    ]
    if builtin:
        lines += ["", f"Builtin richer API: ``{builtin}``"]
    lines += [
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from pathlib import Path",
        "from typing import Any, Mapping, Optional",
        "",
        "from ux_channel.render.placement import Placement",
        "",
        f'PACKAGE = "{pkg}"',
        f"METHODS = ({methods_t},)",
        f'CLASS_NAME = "{cls}"',
        f"MOUNT_PROP_KEYS = ({prop_tuple},)" if prop_names else "MOUNT_PROP_KEYS = ()",
        "",
        "",
        f"class {cls}:",
        f'    """Generated preset for {pkg}.',
        "",
        f"    widgets = {cls}(ch)",
        "    w = widgets('id', **mount_props_from_contract)",
        "    return w.commit(**mount_props_from_contract)",
        '    """',
        "",
        "    package = PACKAGE",
        "    mount_prop_keys = MOUNT_PROP_KEYS",
        "",
        "    def __init__(",
        "        self,",
        "        ch: Any,",
        "        id: str | None = None,",
        "        *,",
        "        props: Optional[Mapping[str, Any]] = None,",
        "        auto_register: bool = True,",
        "        **mount_kwargs: Any,",
        "    ) -> None:",
        "        if ch is None:",
        '            raise ValueError("requires Channel from Channel.boot")',
        "        self.ch = ch",
        "        # props = only package fields (contract mount_props + free kwargs)",
        "        base = dict(props or {})",
        "        base.update(mount_kwargs)",
        "        self._default_props: dict[str, Any] = base",
        "        if id is None:",
        '            self.id = ""',
        "            self._factory = True",
        "            self._props = dict(self._default_props)",
        "            return",
        "        if not str(id).strip():",
        "            raise ValueError(\"island id is required; use Cls(ch) then widgets(id=...)\")",
        "        self._factory = False",
        "        self.id = str(id).strip()",
        "        self._props = dict(self._default_props)",
        "        if auto_register:",
        "            self.register()",
        "",
        f'    def __call__(self, id: str, **kwargs: Any) -> "{cls}":',
        '        if not id or not str(id).strip():',
        '            raise ValueError("island id required")',
        "        props = dict(self._default_props)",
        "        if 'props' in kwargs and isinstance(kwargs.get('props'), Mapping):",
        "            props.update(kwargs.pop('props'))",
        "        props.update(kwargs)  # contract fields: " + (", ".join(prop_names) or "any") ,
        f"        return {cls}(self.ch, str(id).strip(), props=props)",
        "",
        "    def _require_island(self) -> None:",
        "        if getattr(self, '_factory', False) or not self.id:",
        "            raise TypeError(",
        f'                "{cls}(ch) is a factory — call widgets(\'id\', …) first"',
        "            )",
        "",
        f'    def register(self) -> "{cls}":',
        '        self.ch.bridge.register(PACKAGE, methods=METHODS, description=f"preset:{PACKAGE}")',
        "        cpath = Path(__file__).with_name('contract.json')",
        "        if cpath.is_file():",
        "            try:",
        "                self.ch.bridge.load_contract(cpath)",
        "            except Exception:",
        "                pass",
        "        return self",
        "",
        f'    def configure(self, **props: Any) -> "{cls}":',
        "        self._require_island()",
        "        self._props.update(props)",
        "        return self",
        "",
        "    def props(self) -> dict[str, Any]:",
        "        self._require_island()",
        "        return dict(self._props)",
        "",
        "    def mount_spec(self) -> Placement:",
        "        self._require_island()",
        "        return self.ch.bridge.mount_spec(self.id, package=PACKAGE, props=self.props())",
        "",
        "    def mount_ops(self) -> list:",
        "        self._require_island()",
        "        return self.ch.bridge.mount_ops(self.id, PACKAGE, props=self.props())",
        "",
        "    def update_ops(self) -> list:",
        "        self._require_island()",
        "        return self.ch.bridge.update_ops(self.id, self.props())",
        "",
        "    def update(self, **props: Any) -> list:",
        "        if props:",
        "            self.configure(**props)",
        "        return self.update_ops()",
        "",
        "    def call(self, method: str, *args: Any, **kwargs: Any) -> list:",
        "        self._require_island()",
        "        return self.ch.bridge.call(",
        "            self.id, method, *args, package=PACKAGE, **kwargs",
        "        )",
        "",
        "    def _result_with_ops(self, ops: list, *, notice: str | None = None) -> Any:",
        "        from ux_channel.protocol.types import Result",
        "        base = self.ch.done(notice=notice) if notice else self.ch.done()",
        "        return Result(ok=True, ops=list(base.ops or []) + list(ops), meta=dict(base.meta or {}), v=getattr(base, 'v', None) or '1')",
        "",
        "    def commit(self, **props: Any) -> Any:",
        '        """Success Result + bridge ops (package props only)."""',
        "        notice = props.pop('notice', None) if props else None",
        "        ops = self.update(**props) if props else self.update_ops()",
        "        return self._result_with_ops(ops, notice=notice)",
        "",
        "    def commit_call(self, method: str, *args: Any, notice: str | None = None) -> Any:",
        "        return self._result_with_ops(self.call(method, *args), notice=notice)",
        "",
        "    def commit_mount(self, *, notice: str | None = None) -> Any:",
        "        return self._result_with_ops(self.mount_ops(), notice=notice)",
        "",
    ]
    # Named package methods from contract method_specs
    method_specs = spec.get("method_specs") if isinstance(spec.get("method_specs"), dict) else {}
    if not method_specs:
        # rebuild from methods list with empty args
        method_specs = {m: {"args": [], "description": f"Adapter method {m}"} for m in methods}
    lines.extend(_render_named_methods(method_specs, cls))
    lines += [
        "    def describe(self) -> dict[str, Any]:",
        "        if getattr(self, '_factory', False):",
        "            return {",
        "                'mode': 'factory',",
        "                'class': CLASS_NAME,",
        "                'package': PACKAGE,",
        "                'mount_prop_keys': list(MOUNT_PROP_KEYS),",
        "            }",
        "        return {",
        '            "mode": "island",',
        '            "class": CLASS_NAME,',
        '            "package": PACKAGE,',
        '            "id": self.id,',
        '            "methods": list(METHODS),',
        '            "mount_prop_keys": list(MOUNT_PROP_KEYS),',
        '            "props": self.props(),',
        '            "ui": "Style the host in ux-dom; package style fields only if in mount_props",',
        "        }",
        "",
        "",
        f"def create(ch: Any, id: str | None = None, **props: Any) -> {cls}:",
        f"    if id is None:",
        f"        return {cls}(ch, props=props)",
        f"    return {cls}(ch, id, props=props)",
        "",
    ]
    return "\n".join(lines)



def module_name_for(package: str, catalog_key: str = "") -> str:
    """Importable package dir: chart.js → chartjs, my-lib → my_lib."""
    if catalog_key and catalog_key not in ("chart.js",):
        base = catalog_key.replace("-", "_")
    else:
        base = slugify(package).replace("-", "_")
    base = re.sub(r"[^0-9a-zA-Z_]", "_", base)
    if base and base[0].isdigit():
        base = "pkg_" + base
    return base or "bridge_pkg"


def write_bridges_index(bridges_root: Path) -> Path:
    """Write bridges/__init__.py re-exporting generated presets."""
    bridges_root = Path(bridges_root)
    bridges_root.mkdir(parents=True, exist_ok=True)
    exports: list[tuple[str, str, str]] = []
    for meta_path in sorted(bridges_root.glob("*/PRESET.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        mod = meta_path.parent.name
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", mod):
            continue
        cls = meta.get("class") or "Bridge"
        exports.append((mod, str(cls), str(meta.get("package") or "")))

    lines = [
        '"""Auto-generated bridge presets — data/ops only; hosts live in ux-dom."""',
        "from __future__ import annotations",
        "",
        "__all__: list[str] = []",
        "",
    ]
    for mod, cls, pkg in exports:
        lines.append(f"from bridges.{mod} import {cls}  # {pkg}")
        lines.append(f"__all__.append({cls!r})")
        lines.append("")
    if not exports:
        lines.append("# uxchannel bridge preset <name> --out bridges")
        lines.append("")
    path = bridges_root / "__init__.py"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def create_bridge_preset(
    dest: Path | str,
    name: str,
    *,
    methods: Sequence[str] | None = None,
    npm: str = "",
    npm_import: str = "",
    global_name: str = "",
    force: bool = False,
) -> Path:
    """
    Write an importable bridge preset package::

        bridges/chartjs/{__init__,preset,contract,ux-bridge-*.js}

        from bridges.chartjs import ChartJsBridge
    """
    spec = resolve_preset_spec(
        name,
        methods=methods,
        npm=npm,
        npm_import=npm_import,
        global_name=global_name,
    )
    pkg = spec["package"]
    dest = Path(dest)
    mod = module_name_for(pkg, str(spec.get("catalog_key") or ""))
    if (dest / "preset.py").exists() or dest.name == mod:
        root = dest
    else:
        root = dest / mod

    if root.exists() and not force and any(root.iterdir()):
        raise DxConflictError(
            f"preset directory exists: {root}",
            code="bridge.preset_exists",
            hint="pass --force to overwrite",
            details={"path": str(root)},
        )
    root.mkdir(parents=True, exist_ok=True)

    create_bridge_package(
        root,
        pkg,
        methods=spec["methods"],
        npm_dep=spec["npm"],
        npm_import=spec["npm_import"],
        global_name=spec["global_name"],
        force=True,
        flat=True,
        mount_props=spec.get("mount_props") or None,
        method_specs=spec.get("method_specs") or None,
    )
    cls = class_name_for(pkg)
    (root / "preset.py").write_text(render_preset_py(spec), encoding="utf-8")
    (root / "__init__.py").write_text(
        f'"""Bridge preset for ``{pkg}`` (auto-generated)."""\n'
        f"from .preset import {cls}, PACKAGE, METHODS, create\n"
        f"__all__ = [{cls!r}, 'PACKAGE', 'METHODS', 'create']\n",
        encoding="utf-8",
    )
    (root / "PRESET.json").write_text(
        json.dumps(
            {
                "package": pkg,
                "module": mod,
                "class": cls,
                "methods": list(spec["methods"]),
                "npm": spec["npm"],
                "kind": spec["kind"],
                "catalog_key": spec.get("catalog_key") or "",
                "builtin": spec.get("use_builtin") or "",
                "generator": "uxchannel bridge preset",
                "import": f"from bridges.{mod} import {cls}",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    parent = root.parent
    if parent.name == "bridges" or list(parent.glob("*/PRESET.json")):
        try:
            write_bridges_index(parent)
        except Exception:
            pass

    log = get_log()
    log.ok("wrote bridge preset", path=str(root), package=pkg, class_=cls)
    log.info("import", hint=f"from bridges.{mod} import {cls}")
    log.info(
        "factory",
        hint=f"widgets = {cls}(ch); w = widgets('id', …); return w.commit(…)",
    )
    if spec.get("use_builtin"):
        b = str(spec["use_builtin"])
        log.info("or builtin", hint=f"from {b.rsplit('.', 1)[0]} import {b.rsplit('.', 1)[-1]}")
    log.info("ui", hint="ux-dom host from w.mount_spec().attrs")
    return root
