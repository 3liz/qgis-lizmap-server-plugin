# [![logo](lizmap_server/resources/icons/icon.png "3Liz")][3liz]Lizmap QGIS Server Plugin

[![QGIS.org](https://img.shields.io/badge/QGIS.org-published-green)](https://plugins.qgis.org/plugins/lizmap_server/)
[![Tests 🎳](https://github.com/3liz/qgis-lizmap-server-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/3liz/qgis-lizmap-server-plugin/actions/workflows/ci.yml)

## Environment variables

* `QGIS_SERVER_LIZMAP_REVEAL_SETTINGS`, read
  [docs.lizmap.com documentation](https://docs.lizmap.com/current/en/install/pre_requirements.html#qgis-server-plugins)
* `STRICT_BING_TOS_CHECK` and `STRICT_GOOGLE_TOS_CHECK`, if set to `TRUE` (the default value), an API key will be
  checked and required for these layers. If no API key provided in the Lizmap plugin, these layers will be discarded.
  If set to `FALSE`, these layers will be forwarded from QGIS Server to Lizmap Web Client but these layers might not work
  and the TOS from these providers might not be compliant.

## Download

### Stable

* All published versions are available [plugins.qgis.org](https://plugins.qgis.org/plugins/lizmap_server/).
* We **highly** recommend to use [qgis-plugin-manager](https://pypi.org/project/qgis-plugin-manager/) to download and install.
    * `qgis-plugin-manager install 'Lizmap server'`
    * and then **follow** the documentation about the **environment variable** for **security** in the
      [Lizmap documentation](https://docs.lizmap.com/current/en/install/pre_requirements.html#installation).
* Latest release link with the full changelog from the [release page](https://github.com/3liz/qgis-lizmap-server-plugin/releases)

**Remember** that the plugin **must** be updated with each release of Lizmap Web Client with its latest version available.

### Unstable

* The `master` branch can be found on https://packages.3liz.org/ after each commits with a stable link.
* Do not use the link provided by GitHub by default in the top right corner.

You can find help and news by subscribing to the mailing list: https://lists.osgeo.org/mailman/listinfo/lizmap.

For more detailed information, check the [Lizmap Web Client](https://github.com/3liz/lizmap-web-client/) GitHub repository.

#### Lizmap server API

Starting from :
* Lizmap 3.4, the plugin is **highly** recommended.
* Lizmap 3.6, the plugin is **required**.

To enable all features in Lizmap Web Client, read the documentation about the
[environment variable](https://docs.lizmap.com/3.5/en/install/pre_requirements.html#lizmap-server-plugin)
on the QGIS server side.

* lizmap/server.json
* SERVICE=LIZMAP
    * ~REQUEST=GetServerSettings~ deprecated for the JSON URL above
    * REQUEST=GetSubsetString
      * LAYER=
      * LIZMAP_USER_GROUPS=
* SERVICE=EXPRESSION
    * REQUEST=VirtualFields
        * VIRTUALS=
        * FILTER=
        * FIELDS=
        * WITH_GEOMETRY=true
    * REQUEST=replaceExpressionText
        * STRING=
        * STRINGS=
        * FEATURE=
        * FEATURES=
        * FORM_SCOPE=
    * REQUEST=GetFeatureWithFormScope
        * FILTER=
        * FORM_FEATURE=
        * WITH_GEOMETRY=
        * FIELDS=
    * REQUEST=Evaluate
        * EXPRESSIONS=
        * FEATURE=
        * FEATURES=
        * FORM_SCOPE=


Manually running a local QGIS server :

```commandline
QGIS_PLUGINPATH=/home/etienne/dev/qgis/server_plugin_git/lizmap_server/ QGIS_SERVER_LOG_FILE=/tmp/bob.txt QGIS_SERVER_LOG_LEVEL=0 QGIS_SERVER_LIZMAP_REVEAL_SETTINGS=True REQUEST_URI=/lizmap/server.json /usr/lib/cgi-bin/qgis_mapserv.fcgi
```

[3liz]:http://www.3liz.com
