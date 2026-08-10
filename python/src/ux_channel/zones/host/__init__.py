"""Zone / package: **host**

Channel, regions, actions, state — day-1 application surface.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'host'
DESCRIPTION = 'Channel, regions, actions, state — day-1 application surface.'
MEMBERS = {'actions_file': 'File-based action discovery — plug-and-play action modules.', 'catalog': 'Action catalog — machine-readable registry metadata for docs / codegen / OpenAPI', 'config': 'ChannelConfig — environment-shaped security and limits (**ux-channel** 0.1).', 'context': 'ActionContext — request-scoped context for handlers.', 'day1': 'Day-1 public surface — prefer this import style for new application code.', 'dx': 'Channel — the app-facing façade for ux-channel.', 'factory': 'High-level factory — production and development bootstrap.', 'flow': 'Flow — product verbs on Channel: on, done, fail, refresh.', 'hooks': 'Action lifecycle hooks.', 'idempotency': 'Idempotency store for safe action retries.', 'live': 'Live plane — in-process topic → region bindings.', 'nonce': 'Nonce / one-shot capability store.', 'planes': 'Client + db safety helpers for ``ux_channel.state``.', 'recipes': 'Named recipes — copy-paste day-1 patterns (low cognitive load).', 'region_cli': 'CLI handlers for opt-in file-based regions.', 'region_component': 'Class-style Region components — ux-dom-adjacent, low ceremony.', 'region_directory': 'RegionDirectory — opt-in file/package discovery for Region workplaces.', 'regions': 'Regions — morphable SSR slots with stable identity.', 'registry': 'ActionRegistry — the dispatch kernel of ux-channel.', 'ssr_state': '``ssr_state`` — session values (server draft) that drive region re-paint.', 'state': 'State / draft stores — ephemeral UI memory, not your database.', 'state_api': 'Channel state — day-1 flat API (session · client · db guards).', 'testing': 'ChannelTest — low-ceremony tests for actions without raw Intent JSON.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
