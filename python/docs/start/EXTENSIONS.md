# Extension author guide

How to add features **without bloating** core. Policy: [LONGEVITY.md](../../../LONGEVITY.md).

## Pick a door

| Need | Door | Where |
|------|------|--------|
| Cross-cutting Intent policy | **A Hooks** | `registry.before` / `after` |
| New database / cache | **B Stores** | `host.stores` protocol + `redis_extra` style module |
| New codec | **C Wire** | `wire.plugins.register_wire_format` |
| UI island / renderer | **D Bridge** | `bridge.plugins.PluginHub` + entry point `ux_channel.plugins` |
| Non-human caller | **E Plane** | `agent_runtime` / `mcp` / new package under L4 |
| New web framework | **F Adapter** | New package or extra — not root |
| Heavy dependency | **G Extra** | `pyproject` optional extra |

## Never

- Add power names to root `__all__`
- Eager-import L4 planes from `protocol` / `host` / `render` / `security` / `api` at module top level
- Bypass caps for mutating actions
- Put demos under `src/ux_channel/`

## Hooks example (Door A)

```python
@reg.before
def deny_unless_admin(intent, args=None, principal=None, **kw):
    if intent.action.startswith("Admin.") and "admin" not in (principal.roles if principal else ()):
        return ch.fail("forbidden")
    return None
```

## Wire plugin example (Door C)

```python
from ux_channel.wire.plugins import register_wire_format
register_wire_format(MyFormat())
```

## Check before PR

```bash
python3 scripts/check_longevity.py
make verify
```
