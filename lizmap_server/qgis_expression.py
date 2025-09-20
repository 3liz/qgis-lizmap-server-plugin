"""Create Lizmap specific Python Expressions"""

import logging

from qgis.core import (
    QgsExpression,
    QgsFeature,
    QgsMapLayer,
    QgsProject,
    QgsRenderContext,
)
from qgis.utils import qgsfunction

LOGGER = logging.getLogger('Lizmap')
SPACES = '  '


@qgsfunction(
    args='auto', group='Lizmap',
    helpText='Get the list of fields needed to render the layer symbology',
)
def layer_renderer_used_attributes(
        layer_identifier: str,
        feature: QgsFeature,
        parent: QgsExpression,
        ) -> list:
    """
    Return the list of fields (names)
    use to render a vector layer
    """
    # Get layer by ID
    layer = QgsProject.instance().mapLayer(layer_identifier)
    if not layer:
        # Get layer by name if no layer found
        get_layers = QgsProject.instance().mapLayersByName(layer_identifier)
        if len(get_layers) > 0:
            layer = get_layers[0]

    if not layer:
        LOGGER.debug(
                f'Layer "{layer_identifier}" not found in the project')
        return []

    # Layer must be a vector layer
    if layer.type() != QgsMapLayer.VectorLayer:
        LOGGER.debug(
                f'Layer "{layer_identifier}" is not a vector layer')
        return []

    # Get layer renderer
    renderer = layer.renderer()

    # Create render context
    renderContext = QgsRenderContext()
    renderContext.setUseAdvancedEffects(True)

    # Return the attributes used to render the layer
    return list(renderer.usedAttributes(renderContext))
