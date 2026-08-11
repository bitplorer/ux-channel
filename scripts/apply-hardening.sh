#!/usr/bin/env bash
# Apply full hardening onto a clean ux-channel checkout
set -euo pipefail
ROOT="${1:-.}"
cd "$ROOT"
PATCH="patches/0001-production-hardening-authz-seal.patch"
if [ -f "$PATCH" ]; then
  git am "$PATCH"
else
  curl -fsSL -o /tmp/uxc-harden.patch \
    https://raw.githubusercontent.com/bitplorer/ux-channel/main/patches/0001-production-hardening-authz-seal.patch
  git am /tmp/uxc-harden.patch
fi
echo "Hardening applied. Verify:"
grep -n "NEVER take roles" python/src/ux_channel/host/registry.py || true
grep -n "Fail closed without signing secret" python/src/ux_channel/agent_runtime/runner.py || true
