# AGENTS.md — ux-channel wire-native

Orientation for agents continuing this package.

## North star

```text
Any peer  ── Intent { action, args, cap } ──▶  Any peer
Any peer  ◀── Result { ok, ops[], error } ──  Any peer
```

One IR. JSON floor. Caps authorize. Transports only deliver. Peers > FFI.

## Non-negotiables

1. Do not invent a parallel RPC style.
2. Do not require CXB, trace, or surface-hello for basic interop.
3. Cap tags / CXB field tags are append-only (see `SPEC/BREAKING_CHANGE_POLICY.md`).
4. Keep the public Python surface frozen (`PUBLIC_API_FREEZE.md`) when integrating the full package.
5. Prefer durable contract work over feature sprawl.

## Verify before claiming green

```bash
python3 conformance/harness/validate_json_vectors.py
python3 conformance/harness/validate_cxb_expected.py
cd peers/ux_channel_rs && cargo test --lib
cargo run --bin uxc_check -- ../../conformance
# optional live:
# UXC_PORT=8787 cargo run --bin uxc_peer &
# cargo run --bin uxc_check -- ../../conformance --http http://127.0.0.1:8787
python3 peers/python_forward/forward_to_rust.py --mint-via-peer
```

## Intentional policies (not bugs)

| Policy | Behavior |
|--------|----------|
| Cap required | `Cart.add` always needs a valid cap |
| Present-cap-must-verify | Any Intent with `cap` set is verified, even for open actions |
| HTTP formats | `/ux-channel/action` is JSON only; health lists library `codecs` separately from HTTP `formats` |
| Arg types | Integer fields (`qty`, `by`) reject non-integers (no silent string→default) |
| Morph HTML | Free-form strings in morph HTML are escaped |

## Where to change things

| Need | Path |
|------|------|
| IR types | `peers/ux_channel_rs/src/types.rs` |
| Cap crypto | `peers/ux_channel_rs/src/cap.rs` |
| CXB | `peers/ux_channel_rs/src/cxb.rs` |
| Dispatch | `peers/ux_channel_rs/src/actions.rs` + `peer.rs` |
| HTTP surface | `peers/ux_channel_rs/src/bin/uxc_peer.rs` |
| Conformance | `conformance/` |
| Roadmap next steps | `ux-channel-roadmap.md` |
