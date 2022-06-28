# Changelog

## Unreleased

* Refactor a little the code about access control list
* Fix an issue when the CFG file is updated and already stored in the LRU cache

## 1.0.1 - 2022-05-11

* If QGIS 3.24, use the native function from QGIS server API to fetch the feature ID
* Use LRU Cache when reading the CFG file to avoid multiple access
* Add the Python, Qt, GDAL and Py-QGIS-Server versions in the JSON metadata

## 1.0.0 - 2022-05-11

* First version of the plugin after the split between Lizmap desktop and server plugin
* The source code is the same as Lizmap plugin version 3.7.7
* Fix Python exception when GetFeatureInfo does not have a feature ID
* Raise QGIS minimum version to QGIS 3.10
