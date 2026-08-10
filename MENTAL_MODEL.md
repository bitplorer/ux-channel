# Mental model

## One sentence

The browser never invents business truth. It sends a signed **Intent**; the server runs an **action**, may update **regions**, and returns a **Result** of ordered **ops** the client applies.

```text
Browser                         Host (Channel)
───────                         ─────────────
control / form  ──Intent(+cap)──►  verify cap → action
DOM slots      ◄──Result(ops[])──  morph / toast / navigate / …
```

## Five strata

| # | Stratum | Owns | Does not own |
|---|---------|------|--------------|
| 0 | Wire IR | Intent, Result, ops, error codes | HTML, frameworks |
| 1 | Trust | CapService.mint / verify | Login UI |
| 2 | Host | Channel, actions, regions, state() | Markup |
| 3 | Render | morph HTML, placement, renderers | Business rules |
| 4 | Product | asgi, realtime, bridge, workplace… | Core IR |

## Application loop

```text
boot → region / on → control → runtime → draft / done|fail
```

## Monorepo

| Tree | Role |
|------|------|
| `SPEC/` + `conformance/` | Law + goldens |
| `rust/` | Peer: caps, CXB, Peer, `uxc_check` |
| `python/src/ux_channel/` | Full host library |
| `verify.sh` | health → layout → vectors → gate → rust → uxc_check |

## Package doors

| Intent | Package |
|--------|---------|
| App imports | `ux_channel` / `api` |
| IR + caps | `protocol` |
| Runtime | `host` (+ `stores` backends) |
| DOM output | `render` |
| Codecs | `wire` |
| HTTP mount | `asgi` |
| CSRF / limits | `security` |
| WebRTC | `realtime` |
| Widgets | `bridge` / `bridges` |
| Tooling | `devtools` |

## Confused pairs

| Term | Means |
|------|--------|
| toast | Wire **op** (user-visible notice), not a Python widget |
| state() | Application state API |
| stores | MemoryStateStore etc. |
| Region | One DOM slot |
| RegionBook | Registry of regions |
| mint / verify | Cap API (Rust-parity; not “sign”) |

## Ownership

```text
Channel owns: actions · caps · regions · Result ops · placement DATA
You own:      all HTML
```

See also [python/STABILITY.md](python/STABILITY.md), [python/ONTOLOGY.md](python/ONTOLOGY.md), [STRUCTURE.md](STRUCTURE.md), [NAMING.md](NAMING.md).
