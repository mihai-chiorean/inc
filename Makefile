.PHONY: help test test-cov mypy lint manifest accuracy zip-skill

PYTHON := python3
COVERAGE := coverage
SCRIPTS := skills/staff/scripts skills/staff/bin
TESTS := skills/staff/tests/test_suggest.py \
         skills/staff/tests/test_apply.py \
         skills/staff/tests/test_status.py \
         skills/staff/tests/test_add_remove.py \
         skills/staff/tests/test_add_unit.py \
         skills/staff/tests/test_audit.py \
         skills/staff/tests/test_sync.py \
         skills/staff/tests/test_llm.py
COV_TARGETS := skills/staff/scripts
COV_MIN := 80

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk -F ':.*?## ' '{printf "  %-18s %s\n", $$1, $$2}' || true
	@echo "  test               run all /staff smoke tests"
	@echo "  test-cov           run with coverage; fail if < $(COV_MIN)%"
	@echo "  mypy               type-check the staff scripts (strict)"
	@echo "  lint               mypy + future linters"
	@echo "  manifest           regenerate agent.manifest.yaml (no LLM summaries)"
	@echo "  manifest-llm       regenerate manifest + (re)compute description_summary for changed agents"
	@echo "  accuracy           run the suggest accuracy harness (summary vs full)"

test:
	@for t in $(TESTS); do \
		echo "==> $$t"; $(PYTHON) $$t || exit 1; \
	done

# Coverage with subprocess support: scripts are invoked as subprocesses by
# the test suite, so we set COVERAGE_PROCESS_START + drop sitecustomize.py
# on PYTHONPATH. Each subprocess writes its own .coverage.<pid> data file;
# `coverage combine` merges them at the end.
test-cov:
	@$(COVERAGE) erase
	@COVERAGE_PROCESS_START=$$(pwd)/.coveragerc \
	 PYTHONPATH=$$(pwd)/skills/staff/tests:$$PYTHONPATH \
	 ; for t in $(TESTS); do \
		echo "==> $$t"; \
		COVERAGE_PROCESS_START=$$(pwd)/.coveragerc \
		PYTHONPATH=$$(pwd)/skills/staff/tests:$$PYTHONPATH \
		$(COVERAGE) run --rcfile=.coveragerc $$t || exit 1; \
	done
	@$(COVERAGE) combine
	@$(COVERAGE) report --fail-under=$(COV_MIN) --skip-empty
	@$(COVERAGE) html -d htmlcov >/dev/null 2>&1 && echo "html: htmlcov/index.html" || true

mypy:
	@if $(PYTHON) -m mypy --version >/dev/null 2>&1; then \
		$(PYTHON) -m mypy --config-file pyproject.toml skills/staff/scripts scripts; \
	else \
		echo "mypy not installed; pip install mypy>=1.8 to enable type checking" >&2; \
	fi

lint: mypy

manifest:
	$(PYTHON) scripts/generate-manifest.py

manifest-llm:
	$(PYTHON) scripts/generate-manifest.py --llm-summaries

# Run against labels in skills/staff/tests/labels.yaml (Mihai's curated set).
# Hits the LLM provider for each (project x strategy) combination.
accuracy:
	$(PYTHON) skills/staff/tests/eval_suggest_accuracy.py --labels skills/staff/tests/labels.yaml

# Package a skill folder as a zip for sharing or external distribution.
# Per Anthropic skills guide: skills are folder-based units that can be
# zipped, shared, and unzipped into ~/.claude/skills/. Added via MIT-437.
# Usage: make zip-skill SKILL=staff
zip-skill:
	@if [ -z "$(SKILL)" ]; then echo "usage: make zip-skill SKILL=<name>"; exit 2; fi
	@if [ ! -d "skills/$(SKILL)" ]; then echo "error: skills/$(SKILL) not found"; exit 2; fi
	cd skills && zip -r ../$(SKILL).zip $(SKILL) -x '$(SKILL)/__pycache__/*' '$(SKILL)/*/__pycache__/*' '$(SKILL)/.DS_Store'
	@echo "wrote $(SKILL).zip — recipient unzips into ~/.claude/skills/"
