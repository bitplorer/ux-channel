# Convenience targets — prefer these over remembering commands.
.PHONY: help health verify verify-http peer-demo peer-stop test-rust test-python-host test-python python-path

help:
	@echo "Targets:"
	@echo "  make health       - links + stale paths + required files"
	@echo "  make verify       - health + law + Python + Rust (CI default)"
	@echo "  make verify-http  - verify + live peer + demo forward"
	@echo "  make peer-demo    - start demo uxc_peer (oracle allow-listed)"
	@echo "  make peer-stop    - kill uxc_peer if running"
	@echo "  make test-rust    - cargo test --lib only"
	@echo "  make test-python  - pytest python/tests (interop sync)"
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

sync-python:
	python3 scripts/sync_python_layout.py
	python3 scripts/sync_python_layout.py --check

test-python-host:
	@python3 -c "import fastapi" 2>/dev/null || python3 -m pip install -q fastapi httpx starlette
	PYTHONPATH="$(CURDIR)/python/src:$${PYTHONPATH:-}" python3 -m pytest \
		$(CURDIR)/python/tests/gate \
		$(CURDIR)/python/tests/regions \
		$(CURDIR)/python/tests/core/test_day1_api.py \
		$(CURDIR)/python/tests/core/test_api_surface.py \
		$(CURDIR)/python/tests/core/test_registry.py \
		$(CURDIR)/python/tests/core/test_flow.py \
		$(CURDIR)/python/tests/core/test_control.py \
		$(CURDIR)/python/tests/core/test_capability_regression.py \
		$(CURDIR)/python/tests/state/test_draft_rmw.py \
		$(CURDIR)/python/tests/state/test_ssr_state.py \
		$(CURDIR)/python/tests/state/test_state_flat.py \
		$(CURDIR)/python/tests/state/test_state_depth.py \
		$(CURDIR)/python/tests/dx/test_channel_dx.py \
		-q --tb=line

test-python:
	@python3 -c "import itsdangerous, pytest" 2>/dev/null || python3 -m pip install -q -r "$(CURDIR)/requirements-dev.txt"
	PYTHONPATH="$(CURDIR)/python/src:$${PYTHONPATH:-}" python3 -m pytest "$(CURDIR)/python/tests/gate" -q --tb=line

python-path:
	@echo "export PYTHONPATH=\"$(CURDIR)/python:\$${PYTHONPATH:-}\""
