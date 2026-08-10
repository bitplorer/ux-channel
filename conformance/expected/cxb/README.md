# CXB expected blobs (oracle-frozen)

**Status:** Phase 1 deliverable — frozen golden bytes from the pure-Python
CXB oracle (`ux_channel.wire.cxb.encode_cxb_python`).

| File | Role |
|------|------|
| `*.cxb` | Binary CXB1 (or CXBZ) frames |
| `*.meta.json` | sha256, len, hex, b64 sidecars |
| `index.json` | Manifest consumed by harness / Rust `uxc_check` |

## Regenerate

```bash
# extract reference package if needed, then:
PYTHONPATH=/path/to/ux-channel-0.1.0/src \
  python3 conformance/harness/regenerate_cxb_expected.py
```

## Validate

```bash
python3 conformance/harness/validate_cxb_expected.py
# With oracle: re-encode must be byte-identical to frozen blobs.
# Without oracle: magic + length + sha256 + CRC structural only.
```

## Rules

1. JSON is still the floor — these blobs are the **opt-in** dense path.
2. Do not hand-edit `.cxb` files; re-run the regenerator from the oracle.
3. Tag numbers / op dense keys are append-only (see package `docs/core/CXB.md`).
4. Second implementation (Rust peer) should decode every blob and, when encode
   is ready, match sha256 of encode(source JSON).
