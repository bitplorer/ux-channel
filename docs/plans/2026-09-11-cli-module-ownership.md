---
title: CLI + module ownership map (plan only — no folder moves)
date: 2026-09-11
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: user-ask + TELOS A3/A8 + Framework Lock
execution: plan-artifact-only
channel_tip: b0cc17d87348fa65578f41e95879b35c43b0ecfa
compose_tip: e899ebec70299effae84fa291b10adf122b34e26
---

# CLI + module ownership map

> **This PR ships the plan only.** Do not move folders, do not rename public CLI verbs, do not restyle into Clean Architecture, do not rewrite encyclopedia docs in the same cut.

**For later implementers:** execute the cut order in §6.
Do not start with a `cli/` kit overlay.
Channel already has a composition language (Intent → Result → Cap).
Compose already has a concern→file table (`docs/ARCHITECTURE.md`).
Copy that pattern; do not invent a sixth product.

**Tips inventoried**

| Repo | SHA | Note |
|------|-----|------|
| bitplorer/ux-channel | `b0cc17d87348fa65578f41e95879b35c43b0ecfa` | floor met (`≥ b0cc17d`) |
| bitplorer/ux-compose | `e899ebec70299effae84fa291b10adf122b34e26` | floor met (`≥ e899ebe`); honesty cut after channel #27 |

## Goal Capsule

Categorize so each concern has one owner path (A3).
Findability and flow understanding improve because a reader opens one package for one job — not because folders were renamed to fashion (`cli/`, `services/`, `domain/`).

Stop when: every public CLI verb has one dispatcher + one body owner; ghost packages (`ops/`, `enhance/`) are on the map; L5 scaffolding is not sitting in L2 host; compose leftovers that are still dual doors are named; encyclopedia docs wait until those code cuts ship.

## Product Contract

### Requirements

- R1. Inventory every CLI verb / entry point (uxchannel, console scripts, argparse, rust bins, make/verify) with current `path:line` owner.
- R2. Inventory fragmented / mixed modules (devtools, host, asgi, wire, cek, ops, enhance, …) where ownership is unclear.
- R3. Propose categorization: concern → owner path → stay / move / DEFER. Prefer thin moves that close dual doors.
- R4. Same pass sketch for ux-compose fragments (`wire/`, `kit/`, `serve_dev`, `doctor`) vs channel tip.
- R5. Kill list: fashion folders, public verb renames, docs-first, sixth product, Framework Lock violations.
- R6. Cut order: channel CLI ownership → channel module ownership → compose fragments → docs.

### Constraints (law, not taste)

- A3. One concern → one owner path. Not a drawer named after a layer of a foreign architecture.
- A8. Do not move public CLI verb names unless the name is a lie.
- Framework Lock. Keep Channel's native composition (Intent → Result → Cap, frozen public names in `PUBLIC_API_FREEZE.md`). No Clean Architecture restyle.
- Isolation. Compose product code imports Channel only through `wire/`. Do not punch a second door.
- Docs after the code cut. This plan file is the exception. Do not edit `docs/INDEX.md`, `LAYERS.md`, or encyclopedia pages in the same PR as a move.

### Out of scope (this artifact and the first code cuts)

- Renaming `uxchannel` / `uxcompose` / `uxc_peer` / `uxc_check`.
- Merging `uxchannel create-app` into `uxcompose create-app` (two products).
- Splitting the Python/Rust monorepo.
- Moving HTML/CSS ownership into Channel.
- Replacing `Channel.boot` / `CapService` / `apply_host_adapter`.
- A compose implementation PR in this change.

### Acceptance examples (for later code cuts, not this PR)

- AE1. `python/pyproject.toml` `[tool.poetry.scripts] uxchannel` targets a module that exists.
- AE2. `uxchannel --help` lists the same verb names as today.
- AE3. `make layout` knows `ops/` and `enhance/` (or an explicit DEFER note in PACKAGE_MAP, not silence).
- AE4. `host/region_cli.py` is not an L2 runtime module (moved under L5 or documented as DX-only with a map entry that says so).
- AE5. Compose still has no `cli/` package. `uxcompose` verbs unchanged.

---

## 1. Channel CLI inventory

### 1.1 Public product CLI (A8 freeze: verb names)

Console script claim: `python/pyproject.toml:107` → `uxchannel = "ux_channel.cli:main"`.
**That module does not exist.** Layout law forbids top-level `cli.py` (`PACKAGE_MAP.json` `top_level_modules_forbidden`, `scripts/sync_python_layout.py:320-323`).

Live owners:

| Door | Path | Notes |
|------|------|-------|
| `python -m ux_channel` | `python/src/ux_channel/__main__.py:9` | imports `ux_channel.devtools.cli.main` |
| All tests | `from ux_channel.devtools.cli import main` | never `ux_channel.cli` |
| Installed script (claimed) | `ux_channel.cli:main` | **named lie** — pip entry would fail; `python -m` works |

Dispatcher: `python/src/ux_channel/devtools/cli.py` (`main` at **689**, argparse at **690**, `prog="uxchannel"`).

| Public verb | argparse | Handler | Body owner today |
|-------------|----------|---------|------------------|
| `info` | 717 | `cmd_info` 36 | `devtools/info.py` |
| `check` | 720 | `cmd_check` 53 | inline + `host/config.py` (`ChannelConfig`) |
| `new` | 727 | `cmd_new` 127 | inline string `_SCAFFOLD` in `cli.py:91` |
| `create-app` | 732 | `cmd_create_app` 143 | `scaffold/create.py` |
| `scaffold-check` | 768 | `cmd_scaffold_check` 191 | `scaffold/create.py` `validate_scaffold` |
| `doctor` | 773 | `cmd_doctor` 203 | `Channel.doctor` (`host/channel.py:490`) + `devtools/doctor.py` + host `__init__.py:46` patch |
| `explain` | 793 | `cmd_explain` 250 | `devtools/explain.py` |
| `profile` | 797 | `cmd_profile` 550 | `devtools/profiling.py` |
| `dashboard` | 813 | `cmd_dashboard` 639 | `devtools/dashboard.py` |
| `dx` | 825 | `cmd_dx` 261 | `Channel.describe` / `Channel.help` (`host/channel.py:460,538`) + `host/patterns.py` |
| `templates` | 828 | `cmd_templates` 284 | `scaffold` |
| `recipe` | 831 | `cmd_recipe` 292 | `host/patterns.py` |
| `help-topic` | 837 | `cmd_help_topic` 310 | `Channel.help` |
| `bridge` (+ nested actions) | 841 | `cmd_bridge` 325 | **body lives in cli.py** (~200 lines) calling `bridge/bridge_scaffold.py`, `bridge/bridge_preset_gen.py` |
| `region` (+ nested actions) | 895 | `cmd_region` 319 | `host/region_cli.py:11` (**L5 scaffolding inside L2 host**) |
| `upgrade-check` | 913 | `cmd_upgrade_check` 530 | `devtools/upgrade_check.py` |

Bridge nested actions (same public verb `bridge`, not new A8 names): `explain` \| `help` \| `recipe` \| `catalog` \| `list-presets` \| `new` (= `preset`) \| `preset` \| `generate` \| `gen` \| `methods` \| `list-methods` \| `add-method` \| `add` \| `remove-method` \| `rm-method` \| `remove` \| `list`.

Region nested actions: `recipes` \| `add` \| `list` \| `show` \| `check`.

Global flags (not verbs): `-v/--verbose`, `-q/--quiet`, `--json` at `cli.py:698-714`.

### 1.2 In-process DX (not argv, frozen names)

| Speech | Owner | Role |
|--------|-------|------|
| `Channel.boot` | `host/channel.py:335` → `host/factory.py:41` `create_channel` | One app door |
| `Channel.doctor` | `host/channel.py:490` + `host/__init__.py:46` | Runtime health; CLI prints it |
| `Channel.describe` / `Channel.help` | `host/channel.py:460,538` | Progressive DX |
| `ch.diagnose()` | Channel façade | Plane health (L4) |
| `python -m ux_channel info` | `__main__.py` | Same CLI |

`create_channel` is the factory; `Channel.boot` is the frozen public name.
That is one door with two names on purpose (freeze), not a dual product.

### 1.3 Rust bins (classic peer gate — not Python `uxchannel`)

| Binary | Path | `main` | Job |
|--------|------|--------|-----|
| `uxc_check` | `rust/src/bin/uxc_check.rs` | 25 | Conformance / vectors / optional `--http` |
| `uxc_peer` | `rust/src/bin/uxc_peer.rs` | 88 | HTTP peer `POST /ux-channel/action` (verify-only) |

Declared in `rust/Cargo.toml:27-33`.
Do not fold these under `uxchannel`.
They are the classic peer gate (`OPERATIONAL.md`, ADR 0011).

### 1.4 Operator / maintainer CLIs (not product verbs)

Keep out of the `uxchannel` supercommand unless a name is already a lie.

| Entry | Path | Job |
|-------|------|-----|
| `make verify` / `verify.sh` | `Makefile:41`, `verify.sh` | CI green |
| `make regen` / `layout` / `sync-map` | `Makefile:26-33` | Catalog + PACKAGE_MAP derived fields |
| `make health` | `scripts/repo_health.py` | Links / dead paths |
| `make longevity` | `scripts/check_longevity.py` | Strata |
| `startup-peer.sh` | repo root | Local `uxc_peer` helper |
| `python/scripts/profile_p95.py:1` | alias | **`uxchannel profile`** (documented alias) |
| `python/scripts/soak/harness.py:31` | soak | Load/soak; not a product verb |
| `python/scripts/{bench_wire,fuzz_wire,load_test_channel,bench_cxb_realworld,enterprise_stress_pentest}.py` | argparse `main` | Maintainer benches |
| `demos/python_forward/forward_to_rust.py` | argparse | Demo forward, not a host |

### 1.5 What is wrong (CLI)

`devtools/cli.py` is 953 lines: parser + several verb bodies (`new` scaffold string, `bridge` actions, `check`) sit in the dispatcher.
Compose already solved this: `cli.py` is argv only; each verb body is the library that owns the concern.

The pyproject target `ux_channel.cli:main` is a **lie** (A8 exception: fix the import path, do not rename `uxchannel`).

---

## 2. Channel fragmented / mixed modules

Strata today (`PACKAGE_MAP.json` + `LONGEVITY.md`): L1 protocol · L2 host/render/security/api · L3 wire/asgi/transport/cek · L4 planes · L5 devtools/scaffold/catalog.

Ghosts and mixed owners:

| Cluster | Where | Why ownership is unclear | Size (approx) |
|---------|-------|--------------------------|---------------|
| CLI dispatcher + verb bodies | `devtools/cli.py` | Parser, scaffold string, bridge DX, and config check in one file | 953 loc |
| Region file scaffold | `host/region_cli.py` | L5 DX inside L2 host (24 host files / ~8k loc) | 191 loc |
| Recipes as host runtime | `host/patterns.py` | Copy-paste DX living next to `Channel` / `ActionRegistry` | — |
| Doctor triple door | `Channel.doctor` + `devtools/doctor.py` + `host/__init__.py` monkeypatch | Same checklist, three call sites | — |
| Ghost `ops/` | `python/src/ux_channel/ops/` (4 files) | On disk, gated by tests, **absent from `PACKAGE_MAP.packages`** | 297 loc |
| Ghost `enhance/` | `python/src/ux_channel/enhance/` (10 files) | Same: real plane, layout automation does not see it | 1005 loc |
| Three Op languages | `protocol/ops.py` (wire dicts) · `ops/catalog.py` (`Op` class) · `cek/effects.py` (`Node` / EffectGraph) | Same words `morph`/`toast`/`navigate`, three types | — |
| Two `encode` words | `protocol/encode.py` (handler return → `Result`) · `wire` `encode` (IR → bytes) · `cek/encode.py` (handshake nouns) | Homonyms, not dual products | — |
| HTTP action adapters | `asgi/fastapi.py` (1609) · `asgi/starlette.py` (`mount_channel` alias 203) · `asgi/core.py:38` `handle_action_asgi` · `asgi/pipeline.py` | Door F needs FastAPI + Starlette; `pipeline.py` is the shared preflight (good) | 2355 loc package |
| Enhance HTTP | `enhance/asgi_wire.py` (pure) · `asgi/enhance_routes.py` (FastAPI mount) | Already split correctly | thin |
| Cap machines | `protocol/capability.py` `CapService` · `cek/host_adapter.py` `CekHostCapService` · rust `cap.rs` | Law, not clutter — keep | — |
| Agent façade vs kernel | `devtools/agents_api.py` (`agents(ch)`) · `agent_runtime/` | Façade in L5, kernel in L4 — same pattern as compose `cli.py` vs `doctor.py` | — |
| MCP vs agents vs workplace | `mcp/` · `agent_runtime/` · `workplace/` | Three L4 planes, same registry — keep separate | — |
| Channel UI kit vs product UI | `components/` (~2.5k) vs ux-dom vs compose `kit/` | Optional Channel kit; not the product path | — |
| Render demo kit used by CLI | `render/kit.py` (`demo_page`, imported by `cli.py:26`) | L2 render carrying L5 demo HTML helpers | 353 loc |
| Dead stub | `host/_ch_g0.py` | "removed — was a PLACEHOLDER"; nothing imports it | 1 line |
| `asgi/fastapi.py` blob | FastAPI mount + lots of HTTP chrome | Large, but one Door F owner | 1609 loc |
| `host/registry.py` + `host/channel.py` | Registry vs façade | Large but correct split | 1228 + 932 |

`make layout` only errors on **unmapped files inside packages already in the map**.
Whole extra directories (`ops/`, `enhance/`) are invisible.
That is the dual door: disk vs map.

Homonyms that must **not** be "fixed" by rename (Framework Lock / freeze):

| Word | Channel meaning | Other meaning |
|------|-----------------|---------------|
| `wire` | JSON/CXB codecs (`ux_channel.wire`) | Compose isolation door (`ux_compose.wire`) |
| `doctor` | `uxchannel doctor` / `Channel.doctor` | `uxcompose doctor` / `uxdom doctor` |
| `create-app` | Channel demo scaffold | Compose product scaffold |
| `host` | Channel runtime package | Compose Clock A HTTP product host |
| `Op` | Wire dict (`protocol.ops`) | Wave A class (`ops.Op`) · EffectGraph `Node` · ux-behavior `Op` |

---

## 3. Proposed categorization (channel)

Pattern to copy (already proven in compose `docs/ARCHITECTURE.md`):
**one argv dispatcher + verb bodies live with the concern that is also a library.**
Do **not** add `python/src/ux_channel/cli/`.

```text
uxchannel (public name, frozen)
    └─ dispatch: ux_channel.devtools.cli:main   ← tell pyproject the truth
         ├─ info           → devtools.info
         ├─ check          → host.config (validate only)
         ├─ new            → scaffold (single-file helper; drop inline string)
         ├─ create-app     → scaffold.create
         ├─ scaffold-check → scaffold.validate_scaffold
         ├─ templates      → scaffold.available_templates
         ├─ doctor         → Channel.doctor + devtools.doctor (no third patch if avoidable)
         ├─ explain        → devtools.explain
         ├─ profile        → devtools.profiling
         ├─ dashboard      → devtools.dashboard
         ├─ upgrade-check  → devtools.upgrade_check
         ├─ dx / help-topic→ Channel.describe / Channel.help
         ├─ recipe         → host.patterns  OR  scaffold/recipes (see move)
         ├─ bridge *       → bridge.bridge_scaffold + bridge_preset_gen (cli stays thin)
         └─ region *       → L5 region scaffold (leave host.regions as runtime)
```

### 3.1 Stay (do not move)

| Concern | Owner path | Why |
|---------|------------|-----|
| Public CLI name `uxchannel` | console script name | A8 |
| Every verb string in the table in §1.1 | argparse `add_parser("…")` | A8 |
| Intent / Result / CapService / `Channel.boot` | `protocol/`, `host/` | Framework Lock |
| JSON floor + CXB | `wire/` | L3 codecs; compose `wire/` is a different law |
| FastAPI / Starlette mount | `asgi/` | Door F |
| Cap Host wrap | `cek/` | ADR 0008–0011; not a tidy |
| `agents(ch)` façade | `devtools/agents_api.py` | L5 façade over L4 kernel |
| Agent kernel | `agent_runtime/` | L4 |
| MCP / workplace / realtime / bridges | their packages | L4 planes |
| `components/` | L4 optional kit | Not product UI; do not merge with compose `kit/` |
| Rust `uxc_peer` / `uxc_check` | `rust/src/bin/` | Peer gate |
| `create_channel` behind `Channel.boot` | `host/factory.py` | Internal factory, frozen boot name |
| Enhance split `asgi_wire` vs `enhance_routes` | already A3 | Thin FastAPI wrap over pure helpers |
| `asgi/pipeline.py` shared preflight | already A3 | HTTP JSON honesty lives here |

### 3.2 Move (thin — closes a dual door)

| What | From | To | Why |
|------|------|----|-----|
| Console script target | `ux_channel.cli:main` (missing) | `ux_channel.devtools.cli:main` | Named lie. Layout forbids top-level `cli.py`. |
| Bridge verb body | `devtools/cli.py` `cmd_bridge` | keep calling `bridge/bridge_scaffold.py` + `bridge_preset_gen.py`; cli.py becomes `args → fn` | Dispatcher must not own npm-bridge DX |
| Single-file `new` template | `_SCAFFOLD` string in `cli.py` | `scaffold/` | Scaffold owns scaffolds |
| Region file generator | `host/region_cli.py` | `scaffold/region_cli.py` (or `devtools/region_cli.py`) | L5 out of L2. `host/regions.py` / `region_directory.py` stay |
| Ghost packages onto the map | disk-only `ops/`, `enhance/` | `PACKAGE_MAP.json` `packages` + `strata` (`ops` L3-or-L4 composition; `enhance` L4) then `make regen` | Map honesty. Not a folder move. |
| Dead stub | `host/_ch_g0.py` | delete | Nothing imports it |

Optional (same cut or DEFER if import weight fights longevity):

| What | From | To | Why |
|------|------|----|-----|
| Named recipes text | `host/patterns.py` | `scaffold/recipes.py` or `devtools/recipes.py` | Recipes are DX, not dispatch. Keep `Channel.help` as the frozen speech door. |

### 3.3 DEFER (not this program)

| Temptation | Why defer |
|------------|-----------|
| New `cli/` package | Compose folder law: argv is `cli.py`; bodies are libraries. Channel should match. |
| Split `asgi/fastapi.py` (1609) into services | One Door F owner. Split only if a second `/action` policy appears. Prefer extracting helpers *into* `pipeline.py` if FastAPI and Starlette drift. |
| Rename `protocol.encode` vs `wire.encode` | Homonym. Freeze + teach; do not churn public import paths. |
| Merge `protocol.ops` / `ops.Op` / `cek.effects.Node` | Three layers (wire / host composition / L7 graph). Merging invents a sixth product. Map them; do not unify types. |
| Fold `Channel.doctor` into CLI-only | `ch.doctor()` is frozen application speech. |
| Move `render/kit.py` demo helpers | Used by scaffold + CLI; moving now is fashion. |
| Relocate `devtools/agents_api.py` into `agent_runtime` | Would eager-load L4 on `from ux_channel import agents` unless you keep a lazy façade. Longevity tests forbid eager agent kernel. |
| Collapse MCP + agent_runtime + workplace | Different callers, same registry. |
| Merge Channel `components/` into compose `kit/` | Layer cut: compose owns product kit copies; Channel kit is optional demo. |
| Teach `ux_channel.cli` as a public module | Would require a forbidden top-level shim. |
| Encyclopedia / INDEX / LAYERS edits | After the code cut. |
| `host/channel.py` / `host/registry.py` size diet | Not an ownership bug. |

---

## 4. ux-compose fragment sketch (vs channel tip `b0cc17d`)

Compose at `e899ebe` already has the A3 map Channel lacks.
Do **not** restyle compose to look like Channel's current `devtools/` junk drawer.
Do **not** add `src/ux_compose/cli/`.

### 4.1 Compose CLI inventory (A8 freeze)

Console script: `pyproject.toml:50` `uxcompose = "ux_compose.cli:main"` — **this module exists** (`src/ux_compose/cli.py:23`).

| Public verb | Dispatch | Body |
|-------------|----------|------|
| `create-app` | `cli.py:29` → `_create_app:131` | `scaffold.py` `create_app` |
| `build` | `cli.py:31` → `_build:160` | `cli_build.py` (CSS minify wrap; `build.py` is the `build()` orchestra — different concern) |
| `serve` | `cli.py:33` → `_serve:229` | modes below |
| `serve dev` | `_serve` | `serve_dev.py` `run` |
| `serve prod` | `_serve` | `uvicorn.run` (clocks off) |
| `serve restart-channel` | `_serve:246` | `serve_restart.py` |
| `deploy` | `cli.py:35` → `_deploy:386` | `deploy.py` |
| `doctor` | `cli.py:37` → `_doctor:409` | `doctor.py:540` `main` (library `doctor()` + argv) |
| `add` | `cli.py:39` → `_add:70` | `kit/copy.py` |

Leftover argv `create` is already documented as teaching, not a second verb (`cli.py` header; ARCHITECTURE agent leftovers).
Do not revive it.

`uxdom` verbs (`doctor` \| `lint` \| `profile` \| `add`) are a **different product**. Keep.

### 4.2 Compose concern → file (already locked)

From compose `docs/ARCHITECTURE.md` (do not duplicate as `MODULE_MAP.md`):

| Concern | Owner | Must not |
|---------|-------|----------|
| Isolation / Channel import | `wire/boot.py`, `wire/caps.py`, `wire/cek.py` | `ux_channel` outside `wire/` |
| Cap mint | `wire/caps.py` | empty-token dual attrs |
| Product CLI argv | `cli.py` | second verb, clock flags, `cli/` package |
| Build / CSS | `cli_build.py`, `tailwind.py`, `assets.py` | Tailwind on ux-dom |
| HTTP product host | `routing/` | fold FastAPI into DirectoryASGI |
| Serve-dev clocks | `serve_dev.py` + argv in `cli.py` | `--one-process` |
| Store lifecycle | `serve_state.py` | compose `FileStateStore` class (Channel owns stores) |
| Doctor | `doctor.py` | leftover scan as kill |
| Kit catalog / copy | `kit/catalog.py`, `kit/copy.py` | overlay in CATALOG; `kit_construct.py` under `kit/` |
| Kit host seam | `kit_construct.py` (next to `component.py`) | move under `kit/` (copy would rewrite imports) |

### 4.3 What is still mixed (thin leftovers vs channel tip)

Channel tip `#27` locked `ActionRegistry.from_config` Cap machine + HTTP JSON honesty.
Compose `#69` (`e899ebe`) already consumes that (Cap door, store precedence, health formats).
**Do not reopen Isolation Law or Cap Host vs Clock A.**

Remaining fragments worth a later compose cut — still not a folder fashion:

| Fragment | Status | Proposed |
|----------|--------|----------|
| `cli.py` still starts Tailwind watch + tunnel around `serve_dev.run` (`cli.py:318-367`) | argv + process orchestration in one file | **Thin DEFER:** move watch/tunnel start into `serve_dev.py` so `cli.py` is argv-only. Risk: ADR 0005 clock boundaries. Only do it if tests already lock clocks. |
| `doctor.py:540` argparse `main` | Intentional: `cli.py` delegates; `from ux_compose import doctor` is public algebra | **Stay.** Not a dual door. |
| `helpers.py` homemade HTML walker (~410 loc) | Documented residual until ux-dom owns extract | **DEFER.** Do not create `fragment.py`. |
| `build.py` vs `cli_build.py` | Already two concerns (`build()` orchestra vs Tailwind CLI wrap) | **Stay.** |
| `wire/` vs channel `wire/` | Same English word, different laws | **Stay.** Teach; do not rename compose `wire/` (Isolation Law). |
| `kit/` 85 files / ~12k loc | Ownable catalog, not a junk drawer | **Stay.** Growth is copies, not mixed concerns. |
| `dx/probe.py` | One probe for doctor | **Stay.** Do not grow `dx/` into a product. |
| Channel `components/` vs compose `kit/` | Two kits on two layers | **Stay.** Authors `uxcompose add`; they do not import Channel components as the product path. |
| `create-app` on both CLIs | Two products | **Stay.** Channel = demo host scaffold. Compose = product app. |
| `serve_state.py` + Channel `FileStateStore` | Compose prepares `UXCOMPOSE_STATE_STORE`; Channel opens the store | **Stay.** Channel #26/#27 is the store owner. |

### 4.4 Compose kill list (local)

Do not add `cli/`, `helpers/`, `kit/kit_construct.py`, `docs/MODULE_MAP.md`.
Do not import `ux_channel` outside `wire/`.
Do not clock-flag `serve`.
Do not implement FileStateStore in compose.
Do not merge `scan_surfaces` into `DirectoryRoutes.discover`.

---

## 5. Kill list (what NOT to do)

| Do not | Why |
|--------|-----|
| Add `ux_channel/cli/` or `ux_compose/cli/` packages | Fashion drawer. Compose already forbids it. Dispatcher ≠ concern. |
| Add `services/`, `domain/`, `adapters/`, `usecases/` | Clean Architecture restyle. Framework Lock. |
| Rename public verbs (`info`, `doctor`, `create-app`, `bridge`, `region`, `serve`, `add`, …) | A8. None of these names are lies except the **import path** `ux_channel.cli`. |
| Rename `uxchannel` → `ux-channel-cli` or similar | Brand freeze (`NAMING.md`, pyproject description). |
| Invent `ux_channel.cli` as a top-level shim | `top_level_modules_forbidden`. Telling pyproject the truth is the fix. |
| Merge `uxchannel` into `uxcompose` | Two products. Channel is the protocol host library; compose is author composition. |
| Merge `uxc_peer` into `uxchannel` | Rust peer gate vs Python DX. |
| Docs-first encyclopedia (`INDEX.md`, `LAYERS.md`, `FEATURES.md`, compose `ARCHITECTURE.md` rewrites) before the code cut | User constraint. This plan file is the only doc in the first PR. |
| Hand-edit `catalog/catalog.json` or PACKAGE_MAP `modules` / `module_count` | `AUTOMATION.md`. Use `make regen` / `make sync-map`. |
| Reintroduce `zones`, `day1`, `paint`, shims | Forbidden names. |
| Teach Channel `transition.*` | Motion stays droppable. |
| A sixth product ("ux-cli", "ux-dev", "ux-app") | Layer cut. |
| Unify the three Op types | Wire vs composition vs L7. |
| Move folders in the plan PR | This artifact only. |
| Open an implementation PR that renames paths as its first commit | Plan must tip first (this PR). |

---

## 6. Suggested cut order

```text
0. This plan PR (channel)     ← you are here
1. Channel CLI ownership      thin, no public verb changes
2. Channel module ownership   map ghosts + L5 out of host
3. Compose fragments          only leftover dual doors; no cli/ package
4. Docs                       LAYERS / INDEX / FEATURES / compose ARCHITECTURE one-liners
```

### U1. Channel CLI ownership

**Goal:** one dispatcher, honest entry, same verbs.

- Point `[tool.poetry.scripts] uxchannel` at `ux_channel.devtools.cli:main`.
- Keep `__main__.py` importing the same `main`.
- Slim `devtools/cli.py`: argparse + `set_defaults(func=…)` only; `cmd_bridge` becomes a short call into `bridge/`; `_SCAFFOLD` moves to `scaffold/`.
- Tests: existing `python/tests/core/test_main_import_safe.py` (`python -m ux_channel info`); `python/tests/devtools/*` that call `main(["doctor"])` etc. Add one test that the console-script target string in `pyproject.toml` import-resolves (`ux_channel.devtools.cli:main`).
- Do not change help text verb names.

**Verify:** `PYTHONPATH=python/src python -m ux_channel --help`; `pytest python/tests/devtools python/tests/core/test_main_import_safe.py python/tests/bridges/test_bridge_*cli*.py python/tests/foundations/test_golden_path.py`.

### U2. Channel module ownership

**Goal:** map matches disk; L5 scaffolding is not L2.

- Add `ops` and `enhance` to `PACKAGE_MAP.json` `packages` + `strata` + `package_docs` (hand design). Then `make regen` (never hand-edit `modules` / `module_count`).
- Move `host/region_cli.py` → `scaffold/region_cli.py` (or `devtools/region_cli.py`). Update the one import in `devtools/cli.py:320`. Runtime `host/regions.py` / `region_directory.py` stay.
- Delete `host/_ch_g0.py` if still unreferenced.
- Optional: `host/patterns.py` recipes → L5. Only if `Channel.help` / `recipe` tests stay green without eager L4.
- Longevity: `make longevity` + `python/tests/gate/test_longevity_strata.py` must list the new packages.

**Verify:** `make layout longevity`; gate tests for enhance waves (`python/tests/gate/test_enhance_*.py`).

### U3. Compose fragments

**Goal:** keep compose's concern table; close only real dual doors.

- Do this in bitplorer/ux-compose **after** U1–U2, against compose tip `≥ e899ebe`.
- Prefer: keep `cli.py` as argv; optionally pull Tailwind/tunnel start into `serve_dev.py` if ADR 0005 tests already pin clocks.
- Do not add folders. Do not rename verbs. Do not rewrite Isolation Law.
- Doctor leftover tokens stay teaching.

**Verify:** compose `make test314` / `PYTHONPATH=src:. python -m pytest tests/ -q` isolation + CLI regression tests.

### U4. Docs (after the code cuts)

- Channel: `python/src/ux_channel/LAYERS.md` one row for `ops/` and `enhance/`; `python/docs/FEATURES.md` CLI implementation line (`devtools.cli`, not `cli.py`); pyproject entry documented as `ux_channel.devtools.cli:main`.
- Compose: no new `MODULE_MAP.md`. At most a one-line pointer that channel CLI now matches compose's dispatcher pattern.
- Do not rewrite START_HERE mid-cut.

### Verification Contract (when cuts run)

- `make verify` on channel after U1 and after U2.
- Do not claim green from this plan PR (no code).
- Compose U3 uses compose's own test command, not channel `make verify`.

### Definition of Done (this PR)

- [x] Plan file at `docs/plans/2026-09-11-cli-module-ownership.md`
- [x] Inventories with `path:line`
- [x] Stay / move / DEFER map
- [x] Compose sketch vs channel tip
- [x] Kill list + cut order
- [ ] No folder moves, no implementation, no encyclopedia edits

---

## Planning Contract

### Key technical decisions

- KTD1. Channel CLI owner is `devtools.cli`, not a new `cli/` package and not a forbidden top-level `cli.py`. Rejected: add `ux_channel/cli.py` re-export. Reason: layout law + compose precedent.
- KTD2. The only A8 lie to fix is pyproject `ux_channel.cli:main`. Rejected: keep teaching `ux_channel.cli` as a public module. Reason: the file cannot exist under current layout.
- KTD3. Ghost packages get map entries, not new layer names. `ops` = host-side composition (not wire). `enhance` = L4 additive envelopes. Rejected: fold `ops` into `protocol.ops`. Reason: wire dicts stay L1; Wave A is optional composition.
- KTD4. `host/region_cli.py` moves to L5. Rejected: leave it in host because `ChannelConfig(regions=…)` is nearby. Reason: generating files is scaffold; discovering them is host.
- KTD5. Compose is already categorized. Later compose work is leftover-dual-door only. Rejected: "same folder fashion as channel". Reason: channel should move toward compose, not the reverse.
- KTD6. Homonyms (`wire`, `doctor`, `create-app`, `Op`) stay. Teach after the cut. Rejected: rename compose `wire/` to `channel_door/`. Reason: Isolation Law is the folder.

### Assumptions

- Channel HEAD remains `≥ b0cc17d` (from_config Cap machine + HTTP JSON honesty). Compose `wire/boot.py` already documents boot as the door.
- `make sync-map` will pick up `ops` and `enhance` once they are intentional packages; until then they are ghosts.
- Installed-script breakage (`ux_channel.cli`) may already affect PyPI/editable installs; `python -m ux_channel` is what tests lock.

### Risks

- Moving `region_cli` churns imports in tests/docs. Keep the public verb `uxchannel region`.
- Adding `enhance`/`ops` to strata may trip longevity if someone eager-imports them from core. They must stay off root `__all__`.
- Slimming `cli.py` can break argparse dest names (`bridges`, `region_action`). Characterization tests first.

---

## Appendix. Ownership map (one screen)

```text
PRODUCT SPEECH (frozen)
  uxchannel                 Python DX supercommand
  uxcompose                 Product lifecycle (other repo)
  uxc_peer / uxc_check      Rust classic peer gate
  Channel.boot / doctor     In-process Channel speech

CHANNEL OWNER PATHS
  protocol/     IR + CapService + wire-shaped ops
  host/         Channel, registry, regions, stores, factory
  render/       Morph IR + HTML safety (not product UI)
  security/     CSRF, limits, policy
  wire/         JSON/CXB codecs
  asgi/         HTTP Door F (pipeline = shared preflight)
  cek/          Cap Host wrap (cek-runtime)
  ops/          Wave A composition (map me)
  enhance/      Additive envelopes (map me)
  scaffold/     create-app + (future) region file DX
  devtools/     argv dispatch + audit/profile/dashboard
  L4 planes     agent_runtime mcp workplace bridge bridges realtime components

COMPOSE OWNER PATHS (do not restyle)
  cli.py        argv only
  wire/         only ux_channel / CEK import
  routing/      Clock A HTTP product host
  serve_dev.py  origin + ui + channel clocks
  doctor.py     library + argv
  kit/          ownable copies
  kit_construct.py  stays outside kit/
```
