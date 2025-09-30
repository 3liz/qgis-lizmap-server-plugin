#!/bin/env bash
#
# Install qgis-plugin-ci locallly
#
# This is used  for installing qgis-plugin-ci package
# in Github actions as workaround to git commands failures
# when run in container
#

set -e

docker run --quiet -u $(id -u):$(id -g) --rm -v $(pwd):/src 3liz/qgis-plugin-ci:endeavour cp -aR /install-ci /src/
pip install --quiet -r ./install-ci/requirements.txt
pip install --quiet --no-deps ./install-ci/qgis_plugin_ci-*.whl


