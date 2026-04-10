SHELL:=bash

PYTHON_MODULE=lizmap_server

TESTS=tests

-include .localconfig.mk

#
# Configure
#

# Check if uv is available
$(eval UV_PATH=$(shell which uv))
ifdef UV_PATH
ifdef VIRTUAL_ENV
# Always prefer active environment
ACTIVE_VENV=--active
endif
UV=uv run $(ACTIVE_VENV)
endif

REQUIREMENT_GROUPS= \
	dev \
	tests \
	lint \
	tools \
	$(NULL)

.PHONY: update-requirements

REQUIREMENTS=$(patsubst %,requirements/%.txt, $(REQUIREMENT_GROUPS))

update-requirements: $(REQUIREMENTS)

# Require uv (https://docs.astral.sh/uv/) for extracting
# infos from project's dependency-groups
requirements/%.txt: uv.lock
	@echo "Updating requirements for '$*'"; \
	uv export --format requirements.txt \
		--no-annotate \
		--no-editable \
		--no-hashes \
		--only-group $* \
		-q -o requirements/$*.txt; \


openapi:
	@ $(UV) python -m $(PYTHON_MODULE).api.swagger > $(PYTHON_MODULE)/api/openapi.json

#
# Static analysis
#

LINT_TARGETS=$(PYTHON_MODULE) $(TESTS) $(EXTRA_LINT_TARGETS)

lint:: 
	@ $(UV) ruff check --output-format=concise $(LINT_TARGETS)

lint:: typecheck

lint-preview:
	@ $(UV) ruff check --preview --output-format=concise $(LINT_TARGETS)

lint-fix:
	@ $(UV) ruff check  --fix $(LINT_TARGETS)

format:
	@ $(UV) ruff format $(LINT_TARGETS) 

typecheck:
	@ $(UV) mypy $(PYTHON_MODULE)
	@ $(UV) mypy --python-version 3.10 tests

scan:
	@ $(UV) bandit -r $(PYTHON_MODULE) $(SCAN_OPTS)

#
# Tests
#

test:
	$(UV) pytest -v $(TESTS)/

#
# Test using docker image
#
QGIS_VERSION ?= 3.44
QGIS_IMAGE_REPOSITORY ?= 3liz/qgis-platform
QGIS_IMAGE_TAG ?= $(QGIS_IMAGE_REPOSITORY):$(QGIS_VERSION)
docker-test:
	docker run --quiet --rm --name qgis-lizmap-server-tests \
		--network host \
		--user $$(id -u):$$(id -g) \
		--mount type=bind,source=$$(pwd),target=/src \
		--workdir /src \
		--env QGIS_VERSION=$(QGIS_VERSION) \
		$(QGIS_IMAGE_TAG) .docker/run-tests.sh

#
# Coverage
#

# Run tests coverage
covtest:
	$(UV) coverage run -m pytest $(TESTS)/

coverage: covtest
	@echo "Building coverage html"
	@ $(UV) coverage html


#
# Code managment
#

# Display a summary of codes annotations
show-annotation-%:
	@grep -nR --color=auto --include=*.py '# $*' lizmap_server/ || true

# Output variable
echo-variable-%:
	@echo "$($*)"
