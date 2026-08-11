# Convenience targets — prefer these over remembering commands.
# Policy: AUTOMATION.md — ceremonial outputs are regenerated, not hand-edited.
.PHONY: help health layout longevity regen sync-map verify verify-http peer-demo peer-stop \
	test-rust test-python test-python-gate test-python-host python-path cxb-regen

help:
	@echo "Targets (see AUTOMATION.md):"
	@echo "  make health            - links + stale/dead paths + required files"
	@echo "  make layout            - package map + catalog freshness (CI)"
	@echo "  make regen             - write derived map fields + catalog"
	@echo "  make sync-map          - packages ← disk, then regen (opt-in inventory)"
	@echo "  make longevity         - strata + no eager L4 in core"
	@echo "  make verify            - health + law + Python gate + Rust (CI)"
	@echo "  make verify-http       - verify + live peer + demo forward"
	@echo "  make cxb-regen         - rebuild conformance/expected/cxb from oracle"
	@echo "  make test-rust         - cargo test --lib --tests"
	@echo "  make test-python-gate  - pytest python/tests/gate"
	@echo "  make test-python-host  - pytest host regions/state/core"
	@echo "  make test-python       - full python/tests (heavier)"
	@echo "  make python-path       - print PYTHONPATH for host package"

health:
	python3 scripts/repo_health.py

layout:
	python3 scripts/sync_python_layout.py --check

regen:
	python3 scripts/sync_python_layout.py

sync-map:
	python3 scripts/sync_python_layout.py --sync-map

longevity:
	python3 scripts/check_longevity.py

cxb-regen:
	PYTHONPATH=$(CURDIR)/python/src python3 conformance/harness/regenerate_cxb_expected.py

verify: health layout longevity
	./verify.sh

verify-http: health layout
	./verify.sh --http

test-rust:
	cd rust && cargo test --lib --tests

test-python-gate:
	cd python && PYTHONPATH=src python3 -m pytest tests/gate -q

test-python-host:
	cd python && PYTHONPATH=src python3 -m pytest tests/regions tests/state tests/core -q --tb=line

test-python:
	cd python && PYTHONPATH=src python3 -m pytest tests -q --tb=line

python-path:
	@echo "export PYTHONPATH=$(CURDIR)/python/src:$$PYTHONPATH"

test-python-integration:
	cd python && PYTHONPATH=src python3 -m pytest tests/integration tests/gate/test_cap_properties.py -q

test-python-properties:
	cd python && PYTHONPATH=src python3 -m pytest tests/gate/test_cap_properties.py tests/core/test_wire_properties.py -q
