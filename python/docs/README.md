# Documentation map

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |


Canonical entry: **[index.md](index.md)**.

**Feature encyclopedia (all features, implementations, use cases):** **[FEATURES.md](FEATURES.md)**.

Docs are grouped by plane (same ontology as `tests/`):

```text
docs/
  start/          golden path · API · layers · freeze
  core/           result · errors · wire
  regions/        regions · components
  state/          session · client · SSR
  asgi/           FastAPI · SSE · WebSocket
  bridges/        contracts · plugins · media
  client/         JS · CSRF · interop
  webrtc/         RTC · ICE · security
  workplace/      room · I/O · outbox
  agents/         AX · MCP
  foundations/    quantity · architecture · waves
  security/       audit
  production/     deploy · soak · enterprise
  dx/             scaffold · inspector · examples
```

Historical names (`moat`, `widgets` package, Morph `slot` as IR, `Money`) are **removed** — use `FOUNDATIONS`, `bridges`, `region`, `Quantity`.

- [Concurrency](start/CONCURRENCY.md) — parallel dispatch, bulkhead

- [Stack (ux-dom)](start/STACK.md) — peer package composition
- [Production](production/PRODUCTION.md)
- [Testing](start/TESTING.md)
