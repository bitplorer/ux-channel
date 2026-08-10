#!/bin/sh
# One-command green check for law + both product packages.
# Usage:
#   ./verify.sh           # harnesses + rust tests + uxc_check
#   ./verify.sh --http    # also live peer smoke + demo forward
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

echo "== repo health =="
python3 "$ROOT/scripts/repo_health.py"

echo "== python layout =="
python3 "$ROOT/scripts/sync_python_layout.py" --check

echo "== JSON vectors =="
python3 conformance/harness/validate_json_vectors.py

echo "== CXB expected =="
python3 conformance/harness/validate_cxb_expected.py

echo "== Python host interop (sync with law) =="
if ! python3 -c "import itsdangerous, pytest" 2>/dev/null; then
  python3 -m pip install -q -r "$ROOT/requirements-dev.txt"
fi
PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}" python3 -m pytest "$ROOT/python/tests/gate" -q --tb=line

echo "== Rust unit tests =="
cd rust
cargo test --lib

echo "== uxc_check (in-process) =="
cargo run --quiet --bin uxc_check -- ../conformance

if [ "$HTTP" -eq 1 ]; then
  echo "== live HTTP =="
  cd "$ROOT"
  sh ./startup-peer.sh
  cd rust
  cargo run --quiet --bin uxc_check -- ../conformance --http http://127.0.0.1:8787
  echo "== python forward (demo) =="
  python3 "$ROOT/demos/python_forward/forward_to_rust.py" --mint-via-peer >/dev/null
  echo "python forward: ok"
  echo "== cross-mint Python↔Rust =="
  python3 "$ROOT/scripts/cross_mint_check.py"
fi

echo "All verify checks passed."
