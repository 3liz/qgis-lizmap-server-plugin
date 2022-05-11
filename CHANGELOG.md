# Changelog

## Unreleased

* Provide the Py-QGIS-Server version if possible in the JSON metadata
* Use LRU Cache when reading the CFG file to avoid multiple access

## 1.0.0 - 2022-05-11

* First version of the plugin after the split between Lizmap desktop and server plugin
* The source code is the same as Lizmap plugin version 3.7.7
* Fix Python exception when GetFeatureInfo does not have a feature ID
* Raise QGIS minimum version to QGIS 3.10
