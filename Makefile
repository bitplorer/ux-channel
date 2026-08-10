# Convenience targets — prefer these over remembering commands.
.PHONY: help health verify verify-http peer-demo peer-stop test-rust python-path

help:
	@echo "Targets:"
	@echo "  make health       - links + stale paths + required files"
	@echo "  make verify       - full law + rust checks (CI default)"
	@echo "  make verify-http  - verify + live peer + demo forward"
	@echo "  make peer-demo    - start demo uxc_peer (oracle allow-listed)"
	@echo "  make peer-stop    - kill uxc_peer if running"
	@echo "  make test-rust    - cargo test --lib only"
	@echo "  make python-path  - print PYTHONPATH export for host package"

health:
	python3 scripts/repo_health.py

verify: health
	./verify.sh

verify-http: health
	./verify.sh --http

peer-demo:
	sh ./startup-peer.sh
	@echo "peer up: http://127.0.0.1:8787/ux-channel/health"

peer-stop:
	-pkill -f 'target/debug/uxc_peer' 2>/dev/null || true
	@echo "stopped (if any)"

test-rust:
	cd rust && cargo test --lib

python-path:
	@echo "export PYTHONPATH=\"$(CURDIR)/python:\$${PYTHONPATH:-}\""
