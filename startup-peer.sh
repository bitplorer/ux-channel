#!/bin/sh
# Idempotent local helper: start uxc_peer on 8787 if health is down.
# Workspace preview uses /workspace/startup.sh (8080 + 8787).
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
cd "$ROOT/peers/ux_channel_rs"
if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8787/ux-channel/health; then
  exit 0
fi
export UXC_HOST=0.0.0.0
export UXC_PORT=8787
if [ -x target/debug/uxc_peer ]; then
  ./target/debug/uxc_peer >>/tmp/uxc_peer.log 2>&1 &
else
  cargo run --quiet --bin uxc_peer >>/tmp/uxc_peer.log 2>&1 &
fi
i=0
while [ $i -lt 30 ]; do
  if curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8787/ux-channel/health; then
    exit 0
  fi
  i=$((i + 1))
  sleep 0.2
done
echo "uxc_peer failed to become healthy" >&2
exit 1
