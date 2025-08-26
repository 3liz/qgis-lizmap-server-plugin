#!/bin/bash

set -e

cd /src

VENV=/src/.docker-venv-$QGIS_VERSION

python3 -m venv  $VENV --system-site-packages

echo "Installing required packages..."
$VENV/bin/pip install -q -U --no-cache-dir -r requirements/tests.txt

#export STRICT_BING_TOS_CHECK=True
#export STRICT_GOOGLE_TOS_CHECK=True
#export QGIS_SERVER_CAPABILITIES_CACHE_SIZE=0

cd tests && $VENV/bin/pytest -v $@
