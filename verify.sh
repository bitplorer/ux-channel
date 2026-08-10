#!/bin/sh
# One-command green check for the wire-native package.
# Usage:
#   ./verify.sh           # harnesses + cargo test + uxc_check
#   ./verify.sh --http    # also live HTTP against demo peer on :8787
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
cd "$ROOT"
HTTP=0
for a in "$@"; do
  case "$a" in
    --http) HTTP=1 ;;
    -h|--help)
      echo "Usage: $0 [--http]"
      exit 0
      ;;
  esac
done

echo "== JSON vectors =="
python3 conformance/harness/validate_json_vectors.py

echo "== CXB expected =="
python3 conformance/harness/validate_cxb_expected.py

echo "== Rust unit tests =="
cd peers/ux_channel_rs
cargo test --lib

echo "== uxc_check (in-process) =="
cargo run --quiet --bin uxc_check -- ../../conformance

if [ "$HTTP" -eq 1 ]; then
  echo "== live HTTP =="
  cd "$ROOT"
  sh ./startup-peer.sh
  cd peers/ux_channel_rs
  cargo run --quiet --bin uxc_check -- ../../conformance --http http://127.0.0.1:8787
  echo "== python forward =="
  python3 "$ROOT/peers/python_forward/forward_to_rust.py" --mint-via-peer >/dev/null
  echo "python forward: ok"
fi

echo "All verify checks passed."
