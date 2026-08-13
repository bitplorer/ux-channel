# Inventory — SPEC ↔ code ↔ vectors

| Concern | SPEC | Code path | Vector |
|---------|------|-----------|--------|
| present-cap-must-verify | capability-extension.md | `host.rs` / `arch/dispatch.py` + CapService | `python/tests/gate/test_arch_e2e.py` |
| once replay | capability-extension.md | CapService verify + nonce | `test_cap_once_replay` |
| store down | capability-extension.md | CapService no store → refuse | `test_cap_store_down` |
| unknown meta | flow.md / ADR 0007 | PeerApply ignores meta | `vectors/arch/flow-meta-ignored.json` |
| project classic | project.md | `project.py` / `project.rs` | `vectors/arch/project-classic-only.json` |
| project auto | project.md | same | `vectors/arch/project-auto-web.json` |
| project agent-only | profiles/agent.v1.md | drop morph/navigate | `vectors/arch/project-agent-only.json` |
| proof reject | proof.md | PeerApply + JS `verifyEffectProof` | `test_proofs_roundtrip` |
| single-flight | concurrency.md | PeerApply lock / AtomicBool | `test_single_flight` |
| flow non-authority | flow.md | `flow_id` correlation only | `test_flow_store_and_cap_dispatch` |
| budgets | budgets.md | apply + host emit | `vectors/arch/apply-budget.json` |
| web safeHref | profiles/web.v1.md | drivers + ux-channel.js | driver tests |
| trace.v1 / wire.v1 | profiles/ | `make_trace_drivers` / `make_wire_drivers` | `test_web_v1_extra_ops_and_profiles` |

Empty cells are defects — fill before release.
