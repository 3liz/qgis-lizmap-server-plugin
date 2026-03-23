from typing import (
    Iterator,
)

from qgis.core import (
    QgsLayoutItem,
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
    QgsLayoutPageCollection,
    QgsPrintLayout,
)

from ..schemas.layouts import (
    LayoutDescription,
    LayoutLabel,
    LayoutMap,
    LayoutPage,
    LayoutSummary,
)


def layout_summary(layout: QgsPrintLayout) -> LayoutSummary:
    """Return layout summary"""
    atlas = layout.atlas()
    atlas_enabled = atlas.enabled()
    coverage_layer = atlas.coverageLayer()

    return LayoutSummary(
        name=layout.name(),
        atlas_enabled=atlas_enabled,
        atlas_coverage_layer=coverage_layer.id() if coverage_layer else None,
    )


def layout_pages(collection: QgsLayoutPageCollection) -> Iterator[LayoutPage]:
    """Return iterator to layout page collection"""
    for page in collection.pages():
        size = page.pageSize()
        yield LayoutPage(
            width=size.width(),
            heigth=size.height(),
            units=size.units().name,
        )


def layout_maps(items: list[QgsLayoutItem]) -> Iterator[LayoutMap]:
    """Return iterator to layout Map collection"""
    index = 0
    for item in items:
        if not isinstance(item, QgsLayoutItemMap):
            continue

        size = item.sizeWithUnits()

        linkedMap = None

        overview = item.overview()
        if overview:
            linkedMap = overview.linkedMap()

        yield LayoutMap(
            id_=f"map{index}",  # Match WMS GetCapabilities
            width=size.width(),
            heigth=size.height(),
            uuid=item.uuid(),
            page=item.page(),
            overview_map=linkedMap.uuid() if linkedMap else None,
            grid=item.grids().size() > 0,
        )

        index += 1


def layout_labels(items: list[QgsLayoutItem]) -> Iterator[LayoutLabel]:
    """Return iterator to layout labels collection"""
    for item in items:
        if not isinstance(item, QgsLayoutItemLabel):
            continue

        yield LayoutLabel(
            id_=item.id(),
            html_state=item.mode() == QgsLayoutItemLabel.ModeHtml,
            text=item.text(),
        )


def layout_description(layout: QgsPrintLayout) -> LayoutDescription:
    """Return layout details"""
    atlas = layout.atlas()
    atlas_enabled = atlas.enabled()
    coverage_layer = atlas.coverageLayer()

    items = layout.items()

    return LayoutDescription(
        name=layout.name(),
        atlas_enabled=atlas_enabled,
        atlas_coverage_layer=coverage_layer.id() if coverage_layer else None,
        pages=list(layout_pages(layout.pageCollection())),
        maps=list(layout_maps(items)),
        labels=list(layout_labels(items)),
    )
