#
# Makefile for building/packaging qgis for lizmap hosting
#
.PHONY: package dist

ifndef FABRIC
FABRIC:=$(shell [ -e .fabricrc ] && echo "fab -c .fabricrc" || echo "fab")
endif

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

PACKAGE=lizmap_server_qgis_plugin
PACKAGEDIR=lizmap_server


build2/$(PACKAGEDIR):
	@rm -rf build2/$(PACKAGEDIR)
	@mkdir -p build2
	(cd build2/; unzip ../../lizmap_server.${CI_COMMIT_REF_NAME}.zip)
	chmod -R og+r build2/lizmap_server/


package: build2/$(PACKAGEDIR)
	@echo "Building package $(PACKAGE)"
	$(FABRIC) package:$(PACKAGE),versiontag=$(VERSION),files=$(PACKAGEDIR),directory=./build2

clean:
	@rm -r build2
