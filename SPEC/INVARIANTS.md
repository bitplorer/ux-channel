# Invariants — testable laws (IR 0.1)

These are the claims that must remain true. Implementations and demos may change;
these must not, except via a major IR version (see `BREAKING_CHANGE_POLICY.md`).

---

## IR shape

1. **Intent** requires `v` and non-empty `action`. Current major: `v == "1"`.
2. **Result** always has `ok: boolean`. When `ok == false`, `error.code` and `error.message` are required.
3. **ops** is always an array (may be empty). Each element has non-empty `op`.
4. Unknown top-level Intent fields are ignored (forward-compatible), not fatal.
5. Optional `trace` / handshake envelopes are never required for basic interop.

## Capability

6. **Present cap must verify** (`present_cap_must_verify`). If `cap` is set (non-empty), verification runs even for open actions.
7. Actions listed as cap-required (this peer: `Cart.add`) fail with `unauthorized` when cap is missing.
8. Cap binds `action` + `args_hash` of sealed args; mismatch → `unauthorized`.
9. Expired / bad signature → `unauthorized`.
10. **once / jti:** when `once=true`, replay of the same `jti` must fail closed.
    Python `CapService.verify` consumes atomically before handlers (no store → refuse).
    Rust `CapService::mint_once` + `NonceStore` on `Peer` (health: `once_jti_enforced: true`).

## Safety / coercion

11. Integer sealed fields used by demo handlers (`qty`, `by`) reject non-integers — no silent string→number coercion.
12. Free-form strings embedded in **morph HTML** and **toast display text** are HTML-escaped (ampersand, angle brackets, double/single quotes).  
    **`signal_set` values stay raw** (semantic data, not markup) — that is intentional, not a hole in #12.
13. Wire/parse failures on the action path still yield a **Result-shaped** body (`ok: false`), not a bare transport error body.

## Wire honesty

14. Health (or equivalent) must not advertise HTTP formats the endpoint does not serve.  
    Library codecs (e.g. CXB) may be listed separately from HTTP `formats`.
15. JSON floor always works. CXB is opt-in.
16. **HTTP status is secondary** to `Result.ok` / `error.code`. This peer maps:  
    `ok` → 200, `unauthorized` → 401, other Result errors → 400, encode failure → 500.  
    Clients must still branch on the Result body (status alone is not the contract).

## Kill criteria (stop the line)

- Any present bogus cap succeeds on an open action.
- Cap-required action succeeds without a cap.
- String `qty` / `by` succeeds without explicit validation.
- Morph (or toast display) injects raw `<script>` from user-controlled free-form text.
- Conformance harness or `uxc_check` goes red on main without an intentional major.
- Health `formats` advertises CXB while `/action` only serves JSON.

## How we prove them

| Invariant | Proved by |
|-----------|-----------|
| 1–5 | `validate_json_vectors.py` + types + `uxc_check` |
| 6–9 | `uxc_check` peer edges + unit tests in `peer` / `cap` |
| 10 | `test_cek_runtime_host.py` + Rust `once_replay_fails` / integration `once_cap_replay_unauthorized` |
| 11–12 | `actions` unit tests + `uxc_check` edges |
| 13–16 | `peer.handle_json` + health JSON + HTTP status mapping + CXB suite |

See also `STRUCTURE.md` (permanent vs moving) and `OPERATIONAL.md` (secrets, env).
