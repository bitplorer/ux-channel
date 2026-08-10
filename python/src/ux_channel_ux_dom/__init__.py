"""Interop glue: **ux-channel** ↔ **ux-dom** (optional, soft deps only).

Brand lines
-----------
| Package | PyPI | Import | CLI |
|---------|------|--------|-----|
| Channel | ``ux-channel`` | ``ux_channel`` | ``uxchannel`` |
| DOM | ``ux-dom`` | ``ux_dom`` | ``uxdom`` |
| Glue | *(ships with ux-channel)* | ``ux_channel_ux_dom`` | — |

Neither core package imports the other. Install both, then::

    pip install ux-channel ux-dom
    from ux_channel_ux_dom import control_ux_dom, tree_to_dict, compile_ux_dom

Layering
--------
* ``ux_channel`` — Intent → Action → Result(ops), caps, morph IR, bridges
* ``ux_dom`` — Document / Component trees, XElement, routing
* ``ux_channel_ux_dom`` — glue only (control attrs, tree→morph, CSRF helpers)

CSRF coexistence
----------------
* **ux-dom** may use host meta (default name ``X-CSRF-TOKEN`` — app-owned).
* **ux-channel** CSRF is the header ``X-Channel: 1`` (always).
* Use ``ux_dom_csrf_meta`` + stock ``ux-channel.js`` (forwards host token when
  present; **never** overwrites the channel header).
"""

from ux_channel_ux_dom.control import control_ux_dom, bind_action
from ux_channel_ux_dom.tree import (
    tree_to_dict,
    compile_ux_dom,
    attenuate_control,
    inject_uids,
    inject_ux_dom,
)
from ux_channel_ux_dom.morph import ux_dom_to_morph_ir, paint_ux_dom_region
from ux_channel_ux_dom.perf import (
    inject_uids_cached,
    CompileCache,
    batch_inject,
    structure_hash,
)
from ux_channel_ux_dom.tree_cap_compile import compile_capability_tree, nest_page
from ux_channel_ux_dom.csrf import (
    CHANNEL_CSRF_HEADER,
    UX_DOM_CSRF_META_NAME,
    assert_csrf_names_do_not_collide,
    channel_and_ux_dom_headers,
    ux_dom_csrf_meta,
)

__all__ = [
    "control_ux_dom",
    "bind_action",
    "tree_to_dict",
    "compile_ux_dom",
    "attenuate_control",
    "inject_uids",
    "inject_ux_dom",
    "ux_dom_to_morph_ir",
    "paint_ux_dom_region",
    "inject_uids_cached",
    "CompileCache",
    "batch_inject",
    "structure_hash",
    "compile_capability_tree",
    "nest_page",
    "ux_dom_csrf_meta",
    "channel_and_ux_dom_headers",
    "assert_csrf_names_do_not_collide",
    "UX_DOM_CSRF_META_NAME",
    "CHANNEL_CSRF_HEADER",
]
