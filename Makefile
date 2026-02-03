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
UV_RUN=uv run $(ACTIVE_VENV)
endif

REQUIREMENT_GROUPS= \
	dev \
	tests \
	lint \
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


#
# Static analysis
#

LINT_TARGETS=$(PYTHON_MODULE) $(TESTS) $(EXTRA_LINT_TARGETS)

lint:: 
	@ $(UV_RUN) ruff check --preview  --output-format=concise $(LINT_TARGETS)

lint:: typecheck

lint-fix:
	@ $(UV_RUN) ruff check --preview --fix $(LINT_TARGETS)

format:
	@ $(UV_RUN) ruff format $(LINT_TARGETS) 

typecheck:
	@ $(UV_RUN) mypy $(PYTHON_MODULE)
	@ $(UV_RUN) mypy --python-version 3.10 tests

scan:
	@ $(UV_RUN) bandit -r $(PYTHON_MODULE) $(SCAN_OPTS)

#
# Tests
#

test:
	$(UV_RUN) pytest -v $(TESTS)/


check-uv-install:
	@which uv > /dev/null || { \
		echo "You must install uv (https://docs.astral.sh/uv/)"; \
		exit 1; \
	}

#
# Test using docker image
#
QGIS_VERSION ?= 3.40
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
	$(UV_RUN) coverage run -m pytest $(TESTS)/

coverage: covtest
	@echo "Building coverage html"
	@ $(UV_RUN) coverage html


#
# Code managment
#

# Display a summary of codes annotations
show-annotation-%:
	@grep -nR --color=auto --include=*.py '# $*' lizmap_server/ || true

# Output variable
echo-variable-%:
	@echo "$($*)"
