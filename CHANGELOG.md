# Changelog

## Unreleased

* Spatial filter - Add the capability to filter the spatial layers data by matching the polygon layer field values with the user login. The behaviour depends on a new configuration option `filter_by_user` for the spatial filter. It will be compatible with LWC >= 3.5.

## 1.0.2 - 2022-06-28

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
