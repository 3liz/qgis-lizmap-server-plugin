# [![logo](lizmap_server/resources/icons/icon.png "3Liz")][3liz]Lizmap QGIS Server Plugin

[![QGIS.org](https://img.shields.io/badge/QGIS.org-published-green)](https://plugins.qgis.org/plugins/lizmap_server/)
[![Tests 🎳](https://github.com/3liz/qgis-lizmap-server-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/3liz/qgis-lizmap-server-plugin/actions/workflows/ci.yml)

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

### Tests

```bash
make tests
```

Manually running a local QGIS server :

```commandline
QGIS_PLUGINPATH=/home/etienne/dev/qgis/server_plugin_git/lizmap_server/ QGIS_SERVER_LOG_FILE=/tmp/bob.txt QGIS_SERVER_LOG_LEVEL=0 QGIS_SERVER_LIZMAP_REVEAL_SETTINGS=True REQUEST_URI=/lizmap/server.json /usr/lib/cgi-bin/qgis_mapserv.fcgi
```

### License

Version: MPL 2.0/GPL 2.0/LGPL 2.1

The contents of this file are subject to the Mozilla Public License Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at http://www.mozilla.org/MPL/

Alternatively, the contents of this file may be used under the terms of either of the GNU General Public License Version 2 or later (the "GPL"), or the GNU Lesser General Public License Version 2.1 or later (the "LGPL"), in which case the provisions of the GPL or the LGPL are applicable instead of those above. If you wish to allow use of your version of this file only under the terms of either the GPL or the LGPL, and not to allow others to use your version of this file under the terms of the MPL, indicate your decision by deleting the provisions above and replace them with the notice and other provisions required by the GPL or the LGPL. If you do not delete the provisions above, a recipient may use your version of this file under the terms of any one of the MPL, the GPL or the LGPL.

Software distributed under the License is distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for the specific language governing rights and limitations under the License.

[3liz]:http://www.3liz.com
