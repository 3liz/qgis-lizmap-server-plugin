#!/bin/bash

set -e

VENV=/src/.docker-venv-$QGIS_VERSION

python3 -m venv  $VENV --system-site-packages

echo "Installing required packages..."
$VENV/bin/pip install -q -U --no-cache-dir -r requirements/tests.txt

cd tests && $VENV/bin/pytest -v $@
