# Monorepo structure

```text
ux-channel/
  SPEC/                 Wire law (Intent / Result / ops / cap)
  conformance/          Golden vectors + harnesses + CXB expected
  rust/                 Peer: CapService, CXB, Peer, uxc_check / uxc_peer
  python/src/ux_channel Host library (application runtime)
  python/tests/gate     Interop + layout freeze (CI)
  python/tests/*        Host suites (regions, state, security, …)
  demos/                Cross-language demos
  scripts/              repo_health, sync_python_layout, cross_mint
  verify.sh / Makefile  One-command green
```

## Python package map (intent → package)

| Intent | Package |
|--------|---------|
| Application imports | `ux_channel` / `ux_channel.api` |
| IR + caps (Rust-parity) | `protocol` |
| Channel, regions, state API | `host` (`stores` = backends) |
| Morph / HTML / renderers | `render` |
| CSRF / limits | `security` |
| JSON/CXB codecs | `wire` |
| FastAPI mount | `asgi` |
| WebRTC | `realtime` |
| Island contracts | `bridge` + `bridges` |
| Audit / CLI | `devtools` |
| Package navigator | `catalog` |

## Verify stack

```text
repo_health → layout → JSON vectors → CXB → pytest gate → cargo test → uxc_check
(+ optional --http peer + cross-mint)
```

See [DOCS.md](DOCS.md), [python/STABILITY.md](python/STABILITY.md), [NAMING.md](NAMING.md).
