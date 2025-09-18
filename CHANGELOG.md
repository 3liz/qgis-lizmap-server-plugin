# Changelog

## Unreleased

## 2.13.5 - 2025-09-18

* Improve support for QJazz

## 2.13.4 - 2025-09-11

* Fix: `legendKeys` has been added in QGIS 3.32 replaced by `legendSymbolItems`

## 2.13.3 - 2025-09-10

* Fix vector layer renderer could be `None`

## 2.13.2 - 2025-09-08

* Fix default categorized rendering when no `LEGEND_ON` and `LEGEND_OFF`
* Add Python based **expressions**. At present, only one expression has been added.
  * `layer_renderer_used_attributes(layer_identifier)` which returns the list of fields
    used by the layer renderer. It will be called by Lizmap Web Client tooltip feature,
    which needs the list of fields used in symbology, as it is required by OpenLayers
    to render the geometries with the SLD style when fields are used in rules.

## 2.13.1 - 2025-05-05

* For "Value Relation" and "Relation Reference", use `represent_value` expression instead.
* Improve PyQt6 compatibility

## 2.13.0 - 2025-04-01

* Raise to QGIS Server 3.28 minimum
* Upgrade Python coding standards
* Allow some virtuals fields to be discarded if not considered safe, used in Lizmap Web Client 3.9
* Drag & Drop popup - improve interface (mimic Lizmap editing form) & display NULL value fields
* Update configuration when used with QJazz https://github.com/3liz/qjazz

## 2.12.0 - 2025-01-06

* Improve the `VIRTUAFIELDS` request of the `EXPRESSION` service:
  * Support a new `LIMIT` parameter to limit the number of features returned
  * Support new `SORTING_FIELD` and `SORTING_ORDER` parameters to set the order
    of the returned features
* Filter by polygon: fix a bug when the QGIS table datasource property is a query
* Remove the use of deprecated methods from the QGIS API
* Support for Qt6
* Tests - Add QGIS 3.40 for testing
* Support for QJazz, instead of Py-QGIS-Server 2

## 2.11.2 - 2024-10-17

* Fix wrong variable in the server information handler

## 2.11.1 - 2024-10-14

* Improve the server information handler

## 2.11.0 - 2024-10-03

* Raise QGIS minimum version to QGIS 3.22
* Even if used with Py-QGIS-Server 1.X, it needs the latest release **1.9.1**
* Add plugin homepage to the `server.json`, it enables HTTP link in the Lizmap Web Client administration interface
* Place text widget in right list according to the Drag&Drop form
* Update HTML tooltip to handle Bootstrap 5 tabs with Lizmap Web Client 3.9
* Add Py-QGIS-Server 2 support

## 2.10.1 - 2024-09-11

* Fix relation ID in tooltip.py

## 2.10.0 - 2024-09-02

* Attribute filter - Allow to have a comma separated list of groups or users, for Lizmap Web Client 3.8 and PostgreSQL layer
* Add tests with a FILTER with apostrophe
* Add log if the relation was not found when generating the tooltip

## 2.9.4 - 2024-06-05

* API key - check for Google or Bing layers without an API key
* Avoid a critical error message which was not needed
* Add missing LICENSE file

## 2.9.2 - 2024-05-27

* Review the `GetLegendGraphic` request about invalid layer, not only for vector
* Improve logging about invalid layer

## 2.9.1 - 2024-05-13

* Review the `GetLegendGraphic` request
* Fix Python error when evaluating a QGIS Expression about fields
* Return a warning icon if the layer is invalid
* Some internal code refactoring

## 2.9.0 - 2024-04-29

* Review the GetLegendGraphic
* Discard invalid layers from Services other than WMS
* WMS GetLegendGraphic JSON: Provide Warning icon for invalid layers
* Fix wrong maptip returned in case of layer short name versus layer name
* Review logging in case of error
* Internal refactoring about tests
* For Lizmap Web Client 3.8 : Extending replaceExpressionText Request with ALL features and GeoJSON format
* Add statistics

## 2.8.6 - 2024-03-18

* GetFeatureInfo - Since QGIS 3.36, when reading a QGS file with an empty string, the variable is not returned

## 2.8.5 - 2024-03-15

* GetLegendGraphic - Fix if the feature count is enabled and the count is equal or greater than 10

## 2.8.4 - 2024-01-31

* GetFeatureInfo - Fix a possible Python error if the item is not a `Layer` item, it can return the correct popup content

## 2.8.3 - 2024-01-29

* Fix issue about the project used when evaluating a `GetMap` request with new features from LWC 3.7

## 2.8.2 - 2024-01-15

* Fix evaluating the QGIS Drag&Drop form in a popup request when the geometry is needed, contribution from @ghtmtt

## 2.8.1 - 2023-09-27

* Support the "text widget" from QGIS 3.30 in the tooltip, contribution from @ghtmtt
* Move the fonts from the server into the JSON metadata

## 2.8.0 - 2023-07-25

* Fix concatenate with number in aggregate in the drag&drop layout popup, contribution from @ghtmtt
* For Lizmap Web Client 3.7.0 minimum
  * Add support for the "Attribute Editor Relation" when generating the tooltip
  * Add new filter for the GetLegendGraphic request
  * Add new parameter `PARENT_FEATURE` when evaluating expression

## 2.7.2 - 2023-05-30

* Fix the QGIS server name with QGIS 3.30 `'s-Hertogenbosch`

## 2.7.1 - 2023-04-13

* Add `FILTER_TYPE` to the `GETSUBSETSTRING` request with different values : `SQL` default value, `SAFESQL` or `EXPRESSION`

## 2.7.0 - 2023-03-16

* Always provide a name with the version 'not found' when fetching the list of plugin

## 1.3.1 - 2023-01-25

* Fix regression from the previous version about Py-QGIS-Server

## 1.3.0 - 2023-01-25

* Return the list of fonts installed on the server. It's useful for QGIS layouts.
* Check if Py-QGIS-Server is really used on the server before returning server metadata

## 1.2.2 - 2022-12-16

* Review the metadata and the warning when the plugin is installed on QGIS desktop
* Review the JSON metadata about Py-QGIS-Server when used with Lizmap Web Client 3.6

## 1.2.1 - 2022-11-28

* Add more metadata in the JSON about Py-QGIS-Server and QGIS Server

## 1.2.0 - 2022-10-03

* Improvement about the filtering by polygon (use a QGIS expression when possible)
* Add a new option to use the centroid for the filtering by polygon. Available in the 3.10.0 version of desktop plugin.
* Fix an issue when fetching information from `metadata.txt` in QGIS Server plugins
* Fix an issue to return Py-QGIS-Server version
* Overpass a bug from QGIS Server about a cache in WFS requests, a fix needs to be done in QGIS Server core
* All plugins versions (stable and unstable) are now available https://packages.3liz.org/pub/server-plugins-repository/

## 1.1.1 - 2022-07-29

* Add the plugin name when fetching metadata from QGIS server.
* Fix an issue when the polygon table has a schema or table name which must be enclosed with double quotes.
* Fix an issue preventing to query the PostgreSQL database to retrieve the ids to filter. Performance could be severely
  degraded for heavy filtered layers.

## 1.1.0 - 2022-07-25

* Spatial filter - Add the capability to filter spatial layers data by matching the polygon layer field values with the
  user login instead of groups only. The behaviour depends on a new configuration option `filter_by_user` for the spatial
  filter. It's compatible with Lizmap Web Client ≥ 3.5. The desktop plugin must be updated as well to version 3.9.0.

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
