# Inventory — SPEC ↔ code ↔ vectors

| Concern | SPEC | Code path | Vector |
|---------|------|-----------|--------|
| present-cap-must-verify | capability-extension.md | Channel registry + Cap façade / classic `CapService` | `python/tests/gate/test_cek_dropin_parity.py` |
| once replay (require) | capability-extension.md / ADR 0006 | cek-runtime Host via `CekHostCapService` | `test_require_once_is_host_owned_channel_store_unused` |
| once replay (classic) | capability-extension.md | `CapService.verify` + Channel `nonce_store` | `test_once_replay_fails_closed_both` (`cek=off`) |
| store down (classic) | capability-extension.md | `CapService` no store → refuse | `test_once_cap_requires_nonce_store` |
| Cap machine identity | ADR 0008–0011 | `cek/host_adapter.py` + `cek/runtime_host.py` | `test_cek_runtime_host.py` / `test_cek_layer_honesty.py` |
| flow non-authority | flow.md / ADR 0007 | `flow_id` → `meta.trace` (`after_cek_cut2`) | `test_flow_id_becomes_trace_on_require_result` |
| EffectGraph L7 | effects.md | `cek/effects.py` + `after_cek_cut2` | `test_effect_graph_*_on_require` |
| project classic | project.md | `cek/project.py` | `test_classic_channel_ops_are_not_s` |
| web safeHref | profiles/web.v1.md | drivers + `static/ux-channel.js` | driver / client tests |
| Peer verify-only | ADR 0011 | `rust/src/peer.rs` | `cargo test --lib --tests` |
| classic mint demo-only | cut #5C | `rust/src/cap.rs` mint + `uxc_peer` demo_html | crate/README banners; `uxc_check` |
| previous_secrets honesty | cut #5D | `cek/runtime_host.py` refuse on require | `test_require_previous_secrets_refuses_loudly` |

Empty cells are defects — fill before release.

Deleted `arch/` / `HostRuntime` / `PeerApply` / `vectors/arch/` paths are
historical ([ADR 0011](ADR/0011-delete-parallel-arch-kernel-cut4.md)).
Effect-proof text: [archive/historical/proof.md](archive/historical/proof.md).
