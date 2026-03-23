from typing import Optional

from qgis.core import QgsCoordinateReferenceSystem

from ..schemas import CrsModel


def to_crs(crs: QgsCoordinateReferenceSystem) -> Optional[CrsModel]:
    return (
        CrsModel(
            auth_id=crs.authid(),
            proj=crs.toProj(),
            srid=crs.postgisSrid(),
            description=crs.description(),
        )
        if crs.isValid()
        else None
    )
