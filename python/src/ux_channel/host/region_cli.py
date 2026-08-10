"""CLI handlers for opt-in file-based regions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ux_channel.devtools.errors import DxUsageError


def cmd_region(args: Any, *, get_log) -> int:
    log = get_log()
    action = (getattr(args, "region_action", None) or "list").lower()
    root = Path(getattr(args, "out", None) or "app/regions")

    if action == "recipes":
        for r in ("default", "payment", "learn", "banner"):
            print(f"  {r}")
        print("\n  uxchannel region add pay/desk --recipe payment")
        return 0

    if action == "add":
        path = getattr(args, "path", None)
        if not path:
            raise DxUsageError(
                "region add requires PATH",
                hint="uxchannel region add pay/desk",
            )
        recipe = getattr(args, "recipe", None) or "default"
        force = bool(getattr(args, "force", False))
        uid_opt = getattr(args, "uid", None)
        rel = str(path).strip("/").replace(".", "/")
        dest = root / (rel + ".py")
        if dest.exists() and not force:
            raise DxUsageError(f"exists: {dest}", hint="use --force")
        dest.parent.mkdir(parents=True, exist_ok=True)
        root.mkdir(parents=True, exist_ok=True)
        if not (root / "__init__.py").exists():
            (root / "__init__.py").write_text("", encoding="utf-8")
        parts = Path(rel).parts
        acc = root
        for part in parts[:-1]:
            acc = acc / part
            acc.mkdir(parents=True, exist_ok=True)
            init = acc / "__init__.py"
            if not init.exists():
                init.write_text("", encoding="utf-8")
        stem = parts[-1].replace("-", "_")
        class_name = "".join(x[:1].upper() + x[1:] for x in stem.split("_"))
        uid = uid_opt or ".".join(parts)
        dest.write_text(_template(class_name, uid, recipe), encoding="utf-8")
        log.ok("region added", path=str(dest), uid=uid)
        print(f"✓ {dest}\n  uid={uid} class={class_name} recipe={recipe}")
        return 0

    if action == "list":
        if not root.exists():
            print(f"(no {root})")
            return 0
        for f in sorted(root.rglob("*.py")):
            if f.name == "__init__.py":
                continue
            rel = f.relative_to(root).as_posix()
            uid = rel[:-3].replace("/", ".")
            print(f"  {rel:40}  {uid}")
        return 0

    if action == "show":
        target = getattr(args, "path", None)
        print(f"region {target}\n  static tree under {root}; live: ch.inspect(...)")
        return 0

    if action == "check":
        errors = 0
        if root.exists():
            for f in root.rglob("*.py"):
                if f.name == "__init__.py":
                    continue
                text = f.read_text(encoding="utf-8")
                for bad in (
                    'session("amount',
                    "session('amount",
                    'state_set("amount',
                    "state_set('amount",
                ):
                    if bad in text:
                        print(f"ERROR {f}: money-like session key")
                        errors += 1
        print("ok" if errors == 0 else f"issues: {errors}")
        return 1 if errors and getattr(args, "strict", False) else 0

    if action == "inspect":
        raise DxUsageError(
            "use ch.inspect(uid) in-process",
            hint="inspect is read-only; wire via app code",
        )

    raise DxUsageError(
        f"unknown region action {action}",
        hint="add | list | show | check | recipes",
    )


def _template(class_name: str, uid: str, recipe: str) -> str:
    if recipe == "payment":
        return f'''"""Payment workplace — select / pay / refund."""
from __future__ import annotations
from typing import Any
from ux_channel.host.region_component import Region


class {class_name}(Region):
    uid = "{uid}"
    singleton = True
    scopes = ("pay",)

    def __init__(self, channel=None, store=None, **kw):
        super().__init__(channel, **kw)
        self.store = store

    def render(self, ctx: Any) -> str:
        step = self.state_get("pay_step", "review")
        sel = self.state_get("selected_order_id", "")
        return (
            f'<div data-channel-id="{{self.uid}}">'
            f"step={{step}} selected={{sel}}</div>"
        )

    def facts(self, principal=None):
        return {{
            "pay_step": self.state_get("pay_step", "review"),
            "selected_order_id": self.state_get("selected_order_id", ""),
        }}

    @Region.action(roles=("clerk", "cashier"), summary="Select order id only")
    def select_order(self, order_id: str = ""):
        self.state_set("selected_order_id", order_id)
        self.state_set("pay_step", "confirm")

    @Region.action(roles=("cashier",), summary="Charge from durable store")
    def pay_order(self, order_id: str = ""):
        oid = order_id or self.state_get("selected_order_id", "")
        if self.store is not None:
            money = self.store.load_payable(oid)
            self.store.mark_paid(oid)
        self.state_set("pay_step", "done")

    @Region.action(roles=("refund",), summary="Refund paid order")
    def refund_order(self, order_id: str = ""):
        if self.store is not None:
            self.store.mark_refunded(order_id or self.state_get("selected_order_id", ""))
        self.state_set("pay_step", "review")
'''
    if recipe == "learn":
        return f'''"""Counter — learn file-based regions."""
from __future__ import annotations
from typing import Any
from ux_channel.host.region_component import Region


class {class_name}(Region):
    uid = "{uid}"

    def render(self, ctx: Any) -> str:
        n = int(self.state_get("n", 0) or 0)
        return f'<div data-channel-id="{{self.uid}}"><strong>{{n}}</strong></div>'

    @Region.action(summary="Increment")
    def inc(self):
        self.state_set("n", int(self.state_get("n", 0) or 0) + 1)

    @Region.action(ax=False, summary="Human-only")
    def toggle_help(self):
        self.state_set("help", not bool(self.state_get("help", False)))
'''
    return f'''"""Region workplace."""
from __future__ import annotations
from typing import Any
from ux_channel.host.region_component import Region


class {class_name}(Region):
    uid = "{uid}"

    def render(self, ctx: Any) -> str:
        return f'<div data-channel-id="{{self.uid}}">{type(self).__name__}</div>'

    @Region.action(summary="Sample action")
    def ping(self):
        self.state_set("pinged", True)
'''
