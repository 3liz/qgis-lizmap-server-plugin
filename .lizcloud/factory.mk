# Makefile for building/packaging qgis for lizmap hosting
#
.PHONY: package dist

ifdef CI_COMMIT_TAG
VERSION=$(CI_COMMIT_TAG)
else
ifdef CI_COMMIT_REF_NAME
VERSION=$(CI_COMMIT_REF_NAME)
else
VERSION=$(shell cat ../lizmap_server/metadata.txt | grep "version=" |  cut -d '=' -f2)
endif
endif

main:
	echo "Makefile for packaging infra components: select a task"

FACTORY_PACKAGE_NAME ?= lizmap_server_qgis_plugin
FACTORY_PRODUCT_NAME ?= lizmap_server

PACKAGE=$(FACTORY_PACKAGE_NAME)
PACKAGEDIR=$(FACTORY_PRODUCT_NAME)

build/$(PACKAGEDIR):
	@rm -rf build/$(PACKAGEDIR)
	@mkdir -p build
	(cd build/; unzip ../../lizmap_server.${CI_COMMIT_REF_NAME}.zip)
	chmod -R og+r build/lizmap_server/

package: build/$(PACKAGEDIR)
	@echo "Building package $(PACKAGE)"
	$(FACTORY_SCRIPTS)/make-package $(PACKAGE) $(VERSION) $(PACKAGEDIR) ./build

clean:
	@rm -r build
