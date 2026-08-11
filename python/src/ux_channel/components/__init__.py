"""
Optional Channel Components kit — not the default product UI path (L4).

Design
    Convenience region/components kit for demos and internal apps. Core
    products should prefer ux-dom + ``ch.control``.

Architecture
    L4 plane — never on root application exports.

Implementation

Import explicitly::

    from ux_channel.components import Badge, Modal

Core apps use ux-dom + ``ch.control``. See docs/COMPONENTS.md and docs/COURSE.md.
"""
from ux_channel.components.badge import Badge
from ux_channel.components.base import ChannelComponent, ChannelKit
from ux_channel.components.compose import (
    Composite,
    Block,
    fragment,
    join_fragments,
    plug,
    stamp_attrs,
)
from ux_channel.components.slots import (
    Slot,
    SlotContext,
    SlotList,
    Slots,
    choose_slot,
    map_slot,
    nest,
    render_fragment,
)
from ux_channel.components.composites import (
    AppShell,
    CartPanel,
    Dashboard,
    DataTable,
    LoginCard,
    MediaCard,
)
from ux_channel.components.confirm import Confirm
from ux_channel.components.counter import Counter
from ux_channel.components.flash import Flash
from ux_channel.components.form import Field, Form
from ux_channel.components.list_view import ListView
from ux_channel.components.modal import Modal
from ux_channel.components.primitive import (
    RegistryHost,
    as_host,
    region_attrs,
    region_button,
    region_morph,
    region_root,
    to_html,
    uid_attr,
    uid_sel,
)
from ux_channel.components.tabs import Tabs
from ux_channel.components.wizard import Step, Wizard

__all__ = [
    # primitives
    "RegistryHost",
    "as_host",
    "region_attrs",
    "region_button",
    "region_morph",
    "region_root",
    "to_html",
    "uid_attr",
    "uid_sel",
    # base
    "ChannelComponent",
    "ChannelKit",
    # widgets
    "Badge",
    "Confirm",
    "Counter",
    "Field",
    "Flash",
    "Form",
    "ListView",
    "Modal",
    "Step",
    "Tabs",
    "Wizard",
    # composition
    "Composite",
    "Block",
    "Slot",
    "render_fragment",
    "nest",
    "map_slot",
    "choose_slot",
    "Slots",
    "SlotList",
    "SlotContext",
    "fragment",
    "join_fragments",
    "plug",
    "stamp_attrs",
    # composites
    "AppShell",
    "CartPanel",
    "Dashboard",
    "DataTable",
    "LoginCard",
    "MediaCard"]
