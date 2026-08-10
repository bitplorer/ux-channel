"""Zone / package: **components**

SUBPACKAGE: optional ChannelComponent kit.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'components'
DESCRIPTION = 'SUBPACKAGE: optional ChannelComponent kit.'
MEMBERS = {'badge': 'Badge — simple count/status pill that morphs in place.', 'base': 'ChannelComponent — optional channel-side UI blocks.', 'compose': 'Composition — Block + Composite on top of ChannelComponent (still 1 MRO step).', 'composites': 'Complex composites — Channel widgets + slots for ux-dom / other libraries.', 'confirm': 'ConfirmButton — dangerous once-cap action with optional modal.', 'counter': 'Counter — drop-in ± / reset widget.', 'flash': 'Flash / banner region for persistent messages.', 'form': 'Validated form component — fields, errors, focus, toast.', 'list_view': 'ListView — searchable / pageable list region.', 'modal': 'Modal / drawer chrome component.', 'primitive': 'Bare-bones Channel region primitives — library-agnostic (Tailwind-like utilities', 'slots': 'Slot composition patterns for Channel Components.', 'tabs': 'Tabs — switch panels via morph.', 'wizard': 'Wizard — multi-step flow with next/back/finish.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
