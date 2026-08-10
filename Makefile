# Convenience targets — prefer these over remembering commands.
.PHONY: help health layout verify verify-http peer-demo peer-stop \
	test-rust test-python test-python-gate test-python-host python-path

help:
	@echo "Targets:"
	@echo "  make health            - links + stale paths + required files"
	@echo "  make layout            - package layout check (no shims)"
	@echo "  make verify            - health + law + Python gate + Rust (CI)"
	@echo "  make verify-http       - verify + live peer + demo forward"
	@echo "  make test-rust         - cargo test --lib"
	@echo "  make test-python-gate  - pytest python/tests/gate"
	@echo "  make test-python-host  - pytest host regions/state/core"
	@echo "  make test-python       - full python/tests (heavier)"
	@echo "  make python-path       - print PYTHONPATH for host package"

health:
	python3 scripts/repo_health.py

layout:
	python3 scripts/sync_python_layout.py --check

longevity:
	python3 scripts/check_longevity.py

verify: health layout longevity
	./verify.sh

verify-http: health layout
	./verify.sh --http

test-rust:
	cd rust && cargo test --lib

test-python-gate:
	cd python && PYTHONPATH=src python3 -m pytest tests/gate -q

test-python-host:
	cd python && PYTHONPATH=src python3 -m pytest tests/regions tests/state tests/core -q --tb=line

test-python:
	cd python && PYTHONPATH=src python3 -m pytest tests -q --tb=line

python-path:
	@echo "export PYTHONPATH=$(CURDIR)/python/src:$$PYTHONPATH"
