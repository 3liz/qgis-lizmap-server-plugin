"""qgis4 support helpers"""

from typing import (
    TypeAlias,
    List,
)

from qgis.core import (
    QgsFeature,
    QgsFields,
    QgsJsonUtils,
)

from qgis.PyQt.QtCore import QT_VERSION_STR

QgsFeatureList: TypeAlias = List[QgsFeature]


QT_VERSION_5 = int(QT_VERSION_STR.partition(".")[0]) < 6

if QT_VERSION_5:
    from qgis.PyQt.QtCore import QTextCodec
    CODEC = QTextCodec.codecForName("UTF-8")

    def QgsJsonUtils_stringToFields(string: str) -> QgsFields:
        return QgsJsonUtils.stringToFields(string, CODEC)

    def QgsJsonUtils_stringToFeatureList(string: str, fields: QgsFields) -> QgsFeatureList:
        return QgsJsonUtils.stringToFeatureList(string, fields, CODEC)
else:
    def QgsJsonUtils_stringToFields(string: str) -> QgsFields:
        return QgsJsonUtils.stringToFields(string)

    def QgsJsonUtils_stringToFeatureList(string: str, fields: QgsFields) -> QgsFeatureList:
        return QgsJsonUtils.stringToFeatureList(string, fields)

