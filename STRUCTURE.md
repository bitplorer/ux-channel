# Monorepo structure

```text
ux-channel/
  SPEC/                 IR / cap + SPEC/architecture/
  conformance/          Golden vectors + CXB + vectors/arch
  rust/                 HostRuntime + PeerApply + classic Peer gate + CXB
  python/src/ux_channel Host library (application runtime)
  python/tests/gate     Interop + layout freeze (CI)
  python/tests/*        Host suites (regions, state, security, …)
  demos/                Cross-language demos
  scripts/              repo_health, sync_python_layout, longevity, cross_mint
  AUTOMATION.md         Ceremonial vs hand-coded policy
  verify.sh / Makefile  One-command green
```

## Permanent vs moving

| Permanent (law / product core) | Moving (replace freely) |
|--------------------------------|-------------------------|
| `SPEC/`, `conformance/` | `demos/`, tutorial examples |
| `python/src/ux_channel/{protocol,host,render,security,api}` | L5 tooling UI, dashboard chrome |
| `rust/` HostRuntime / PeerApply / peer gate | Demo HTML in `uxc_peer` |
| Public freeze names | Scaffold templates |

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
| Package navigator | `catalog` (generated) |

One-liners: `PACKAGE_MAP.json` → `package_docs`. Design policy: [AUTOMATION.md](AUTOMATION.md).

## Verify stack

```text
repo_health → layout (fresh catalog) → longevity → JSON vectors → CXB → pytest gate → cargo test → uxc_check
(+ optional --http peer + cross-mint)
```

```bash
make regen     # write derived
make verify    # CI path
```

See [DOCS.md](DOCS.md), [python/STABILITY.md](python/STABILITY.md), [NAMING.md](NAMING.md).

**Longevity / anti-bloat:** [LONGEVITY.md](LONGEVITY.md)
