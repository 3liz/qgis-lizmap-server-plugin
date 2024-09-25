SHELL:=bash

COMMITID=$(shell git rev-parse --short HEAD)

REGISTRY_URL ?= 3liz

ifdef REGISTRY_URL
	REGISTRY_PREFIX=$(REGISTRY_URL)/
endif

FLAVOR:=3.22

BECOME_USER:=$(shell id -u)

QGIS_IMAGE=$(REGISTRY_PREFIX)qgis-platform:$(FLAVOR)

LOCAL_HOME ?= $(shell pwd)

SRCDIR=$(shell realpath .)

PYTHON_PKG=lizmap_server
TESTDIR=test

tests:
	@mkdir -p $$(pwd)/.local $(LOCAL_HOME)/.cache
	@echo Do not forget to run docker pull $(QGIS_IMAGE) from time to time
	@docker run --rm --name qgis-server-lizmap-test-$(FLAVOR)-$(COMMITID) -w /src/test/ \
		-u $(BECOME_USER) \
		-v $(SRCDIR):/src \
		-v $$(pwd)/.local:/.local \
		-v $(LOCAL_HOME)/.cache:/.cache \
		-e PIP_CACHE_DIR=/.cache \
		-e QGIS_SERVER_LIZMAP_REVEAL_SETTINGS=TRUE \
		-e PYTEST_ADDOPTS="$(TEST_OPTS) --assert=plain" \
		$(QGIS_IMAGE) ./run-tests.sh

.PHONY: test

install-tests:
	pip install -U --upgrade-strategy=eager -r requirements/dev.txt

export QGIS_SERVER_LIZMAP_REVEAL_SETTINGS=TRUE
test: lint
	cd test && pytest -v --qgis-plugins=..

lint:
	@ruff check --output-format=concise $(PYTHON_PKG) $(TESTDIR)

lint-preview:
	@ruff check --preview $(PYTHON_PKG) $(TESTDIR)

lint-fix:
	@ruff check --fix --preview $(PYTHON_PKG) $(TESTDIR)
