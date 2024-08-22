__copyright__ = 'Copyright 2021, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from qgis.core import QgsExpression, QgsMapLayer, QgsProject, QgsVectorLayer
from qgis.server import QgsAccessControlFilter, QgsServerInterface

from lizmap_server.core import (
    get_lizmap_config,
    get_lizmap_groups,
    get_lizmap_layer_login_filter,
    get_lizmap_layers_config,
    get_lizmap_override_filter,
    get_lizmap_user_login,
    is_editing_context,
)
from lizmap_server.filter_by_polygon import (
    ALL_FEATURES,
    NO_FEATURES,
    FilterByPolygon,
    FilterType,
)
from lizmap_server.logger import Logger, profiling
from lizmap_server.tools import to_bool
from lizmap_server.tos_definitions import (
    BING_DOMAIN,
    BING_KEY,
    GOOGLE_DOMAIN,
    GOOGLE_KEY,
    strict_tos_check,
)


class LizmapAccessControlFilter(QgsAccessControlFilter):

    def __init__(self, server_iface: QgsServerInterface) -> None:
        super().__init__(server_iface)

        self.iface = server_iface
        self._strict_google = strict_tos_check(GOOGLE_KEY)
        self._strict_bing = strict_tos_check(BING_KEY)

        Logger.info(f"LayerAccessControl : Google {self._strict_google}, Bing {self._strict_bing}")

    # def layerFilterExpression(self, layer: QgsVectorLayer) -> str:
    #     """ Return an additional expression filter """
    #     # Disabling Lizmap layer filter expression for QGIS Server <= 3.16.1 and <= 3.10.12
    #     # Fix in QGIS Server https://github.com/qgis/QGIS/pull/40556 3.18.0, 3.16.2, 3.10.13
    #     if 31013 <= Qgis.QGIS_VERSION_INT < 31099 or 31602 <= Qgis.QGIS_VERSION_INT:
    #         Logger.info("Lizmap layerFilterExpression")
    #         filter_exp = self.get_lizmap_layer_filter(layer, filter_type=FilterType.QgisExpression)
    #         if filter_exp:
    #             return filter_exp
    #
    #         return super().layerFilterExpression(layer)
    #
    #     message = (
    #         "Lizmap layerFilterExpression disabled, you should consider upgrading QGIS Server to >= "
    #         "3.10.13 or >= 3.16.2")
    #     Logger.critical(message)
    #     return ALL_FEATURES

    def layerFilterSubsetString(self, layer: QgsVectorLayer) -> str:
        """ Return an additional subset string (typically SQL) filter """
        Logger.info("Lizmap layerFilterSubsetString")
        # We should have a safe SQL query.
        # QGIS Server can consider the ST_Intersect/ST_Contains not safe regarding SQL injection.
        filter_exp = self.get_lizmap_layer_filter(layer, filter_type=FilterType.SafeSqlQuery)
        if filter_exp:
            return filter_exp

        return super().layerFilterSubsetString(layer)

    def layerPermissions(self, layer: QgsMapLayer) -> QgsAccessControlFilter.LayerPermissions:
        """ Return the layer rights """
        # Get default layer rights
        rights = super().layerPermissions(layer)

        # Get layer name
        layer_name = layer.name()

        # Get Project
        project = QgsProject.instance()

        # Get request handler
        request_handler = self.iface.requestHandler()

        # Discard invalid layers for other services than WMS
        if not layer.isValid() and request_handler.parameter('service').upper() != 'WMS':
            Logger.info(f"layerPermission: Layer {layer_name} is invalid in {project.fileName()}!")
            rights.canRead = rights.canInsert = rights.canUpdate = rights.canDelete = False
            return rights

        # Get Lizmap user groups provided by the request
        groups = get_lizmap_groups(request_handler)

        # Set lizmap variables
        user_login = get_lizmap_user_login(request_handler)
        custom_var = project.customVariables()
        if custom_var.get('lizmap_user', None) != user_login:
            custom_var['lizmap_user'] = user_login
            custom_var['lizmap_user_groups'] = list(groups)  # QGIS can't store a tuple
            project.setCustomVariables(custom_var)

        # Try to override filter expression cache
        is_wfs = request_handler.parameter('service').upper() == 'WFS'
        if is_wfs and request_handler.parameter('request').upper() == 'GETFEATURE':
            self.iface.accessControls().resolveFilterFeatures([layer])

        datasource = layer.source().lower()
        is_google = GOOGLE_DOMAIN in datasource
        is_bing = BING_DOMAIN in datasource
        if is_google or is_bing:
            Logger.info(f"Layer '{layer_name}' has been detected as an external layer which might need a API key.")

        # Get Lizmap config
        cfg = get_lizmap_config(self.iface.configFilePath())
        if not cfg:
            if is_google:
                rights.canRead = rights.canInsert = rights.canUpdate = rights.canDelete = not self._strict_google
            elif is_bing:
                rights.canRead = rights.canInsert = rights.canUpdate = rights.canDelete = not self._strict_bing
            # Default layer rights applied
            return rights

        # If groups is empty, no Lizmap user groups provided by the request
        # The default layer rights is applied
        if len(groups) == 0 and not (is_google or is_bing):
            return rights

        api_key = cfg['options'].get('googleKey', '')
        if is_google and not api_key and strict_tos_check(GOOGLE_KEY):
            rights.canRead = rights.canInsert = rights.canUpdate = rights.canDelete = False
            Logger.warning(
                f"The layer '{layer_name}' is protected by a licence, but the API key is not provided. Discarding the "
                f"layer in the project {project.baseName()}.",
            )
            return rights

        api_key = cfg['options'].get('bingKey', '')
        if is_bing and not api_key and strict_tos_check(BING_KEY):
            rights.canRead = rights.canInsert = rights.canUpdate = rights.canDelete = False
            Logger.warning(
                f"The layer '{layer_name}' is protected by a licence, but the API key is not provided. Discarding the "
                f"layer in the project {project.baseName()}.",
            )
            return rights

        # Get layers config
        cfg_layers = get_lizmap_layers_config(cfg)
        if not cfg_layers:
            # Default layer rights applied
            return rights

        # Check lizmap edition config
        layer_id = layer.id()
        if cfg.get('editionLayers'):
            if layer_id in cfg['editionLayers'] and cfg['editionLayers'][layer_id]:
                edit_layer = cfg['editionLayers'][layer_id]

                # Check if edition is possible
                # By default not
                can_edit = False
                if edit_layer.get('acl'):
                    # acl is defined and not an empty string
                    # authorization defined for edition
                    group_edit = edit_layer['acl'].split(',')
                    group_edit = [g.strip() for g in group_edit]

                    # check if a group is in authorization groups list
                    if len(group_edit) != 0:
                        for g in groups:
                            if g in group_edit:
                                can_edit = True
                    else:
                        can_edit = True
                else:
                    # acl is not defined or an empty string
                    # no authorization defined for edition
                    can_edit = True

                if can_edit and 'capabilities' in edit_layer and edit_layer['capabilities']:
                    # A user group can edit the layer and capabilities
                    # edition for the layer is defined in Lizmap edition config
                    edit_layer_cap = cfg['editionLayers'][layer_id]['capabilities']

                    rights.canInsert = to_bool(edit_layer_cap['createFeature'])
                    rights.canDelete = to_bool(edit_layer_cap['deleteFeature'])
                    rights.canUpdate = any([
                        to_bool(edit_layer_cap['modifyAttribute']),
                        to_bool(edit_layer_cap['modifyGeometry']),
                    ])

                else:
                    # Any user groups can edit the layer or capabilities
                    # edition for the layer is not defined in Lizmap
                    # edition config
                    # Reset edition rights
                    rights.canInsert = rights.canUpdate = rights.canDelete = False
            else:
                # The layer has no editionLayers config defined
                # Reset edition rights
                Logger.info(
                    f"No edition config defined for layer: {layer_name} ({layer_id})")
                rights.canInsert = rights.canUpdate = rights.canDelete = False
        else:
            # No editionLayers defined
            # Reset edition rights
            Logger.info("Lizmap config has no editionLayers")
            rights.canInsert = rights.canUpdate = rights.canDelete = False

        # Check Lizmap layer config
        if layer_name not in cfg_layers or not cfg_layers[layer_name]:
            # Lizmap layer config not defined
            Logger.info(f"Lizmap config has no layer: {layer_name}")
            # Default layer rights applied
            return rights

        # Check Lizmap layer group visibility
        cfg_layer = cfg_layers[layer_name]
        if 'group_visibility' not in cfg_layer or not cfg_layer['group_visibility']:
            # Lizmap config has no options
            Logger.info(f"No Lizmap layer group visibility for: {layer_name}")
            # Default layer rights applied
            return rights

        # Get Lizmap layer group visibility
        group_visibility = [g.strip() for g in cfg_layer['group_visibility']]

        # If one Lizmap user group provided in request headers is
        # defined in Lizmap layer group visibility, the default layer
        # rights is applied
        for g in groups:
            if g in group_visibility:
                Logger.info(
                    f"Group {g} is in Lizmap layer group visibility for: {layer_name}")
                return rights

        # The lizmap user groups provided gy the request are not
        # authorized to get access to the layer
        Logger.info(
            f"Groups {', '.join(groups)} is in Lizmap layer group visibility for: {layer_name}")
        rights.canRead = False
        rights.canInsert = rights.canUpdate = rights.canDelete = False
        return rights

    def cacheKey(self) -> str:
        """ The key used to cache documents """
        default_cache_key = super().cacheKey()

        # Get Lizmap user groups provided by the request
        groups = get_lizmap_groups(self.iface.requestHandler())

        # If groups is empty, no Lizmap user groups provided by the request
        # The default cache key is returned
        if len(groups) == 0:
            return default_cache_key

        # Get Lizmap config
        cfg = get_lizmap_config(self.iface.configFilePath())
        if not cfg:
            # The default cache key is returned
            return default_cache_key

        # Get layers config
        cfg_layers = get_lizmap_layers_config(cfg)
        if not cfg_layers:
            # The default cache key is returned
            return default_cache_key

        # Check group_visibility in Lizmap config layers
        has_group_visibility = False
        for l_name, cfg_layer in cfg_layers.items():
            # check group_visibility in config
            if 'group_visibility' not in cfg_layer or not cfg_layer['group_visibility']:
                continue

            # clean group_visibility
            group_visibility = [g.strip() for g in cfg_layer['group_visibility']]

            # the group_visibility was just an empty string
            if len(group_visibility) == 1 and groups[0] == '':
                continue

            has_group_visibility = True
            break

        # group_visibility option is defined in Lizmap config layers
        if has_group_visibility:
            # The group provided in request is anonymous
            if len(groups) == 1 and groups[0] == '':
                return '@@'
            # for other groups, removing duplicates and joining
            return '@@'.join(list(set(groups)))

        return default_cache_key

    @profiling
    def get_lizmap_layer_filter(self, layer: QgsVectorLayer, filter_type: FilterType) -> str:
        """ Get lizmap layer filter based on login filter """

        # Check first the headers to avoid unnecessary config file reading
        # Override filter
        if get_lizmap_override_filter(self.iface.requestHandler()):
            return ALL_FEATURES

        # Get Lizmap user groups provided by the request
        groups = get_lizmap_groups(self.iface.requestHandler())
        user_login = get_lizmap_user_login(self.iface.requestHandler())

        # If groups is empty, no Lizmap user groups provided by the request
        if len(groups) == 0 and not user_login:
            return ALL_FEATURES

        # If headers content implies to check for filter, read the Lizmap config
        # Get Lizmap config
        cfg = get_lizmap_config(self.iface.configFilePath())
        if not cfg:
            return ALL_FEATURES

        # Get layers config
        cfg_layers = get_lizmap_layers_config(cfg)
        if not cfg_layers:
            return ALL_FEATURES

        # Get layer name
        layer_name = layer.name()
        # Check the layer in the CFG
        if layer_name not in cfg_layers:
            return ALL_FEATURES

        try:
            edition_context = is_editing_context(self.iface.requestHandler())
            filter_polygon_config = FilterByPolygon(
                cfg.get("filter_by_polygon"),
                layer,
                edition_context,
                filter_type=filter_type,
            )
            polygon_filter = ALL_FEATURES
            if filter_polygon_config.is_filtered():
                if not filter_polygon_config.is_valid():
                    Logger.critical(
                        "The filter by polygon configuration is not valid.\n All features are hidden : "
                        "{}".format(NO_FEATURES))
                    return NO_FEATURES

                # polygon_filter is set, we have a value to filter
                # pass the tuple of groups or the tuple of the user
                # depending on the filter_by_user boolean variable
                groups_or_user = groups
                if filter_polygon_config.is_filtered_by_user():
                    groups_or_user = tuple([user_login])
                polygon_filter, _ = filter_polygon_config.subset_sql(groups_or_user)

        except Exception as e:
            Logger.log_exception(e)
            Logger.critical(
                "An error occurred when trying to read the filtering by polygon.\nAll features are hidden : "
                "{}".format(NO_FEATURES))
            return NO_FEATURES

        if polygon_filter:
            Logger.info(f"The polygon filter subset string is not null : {polygon_filter}")

        # Get layer login filter
        cfg_layer_login_filter = get_lizmap_layer_login_filter(cfg, layer_name)
        if not cfg_layer_login_filter:
            if polygon_filter:
                return polygon_filter
            return ALL_FEATURES

        # Layer login filter only for edition does not filter layer
        is_edition_only = 'edition_only' in cfg_layer_login_filter
        if is_edition_only and to_bool(cfg_layer_login_filter['edition_only']):
            if polygon_filter:
                return polygon_filter
            return ALL_FEATURES

        attribute = cfg_layer_login_filter['filterAttribute']

        # If groups is not empty but the only group like user login has no name
        # Return the filter for no user connected
        if len(groups) == 1 and groups[0] == '' and user_login == '':

            # Default filter for no user connected
            # we use expression tools also for subset string
            login_filter = QgsExpression.createFieldEqualityExpression(attribute, 'all')
            if polygon_filter:
                return f'{polygon_filter} AND {login_filter}'

            return login_filter

        login_filter = self._filter_by_login(
            cfg_layer_login_filter,
            groups,
            user_login,
            layer.dataProvider().name(),
        )
        if polygon_filter:
            return f'{polygon_filter} AND {login_filter}'

        return login_filter

    @staticmethod
    def _filter_by_login(cfg_layer_login_filter: dict, groups: tuple, login: str, provider: str) -> str:
        """ Build the string according to the filter by login configuration.

        :param cfg_layer_login_filter: The Lizmap Filter by login configuration.
        :param groups: List of groups for the current user
        :param login: The current user
        :param provider: The layer data provider ('postgres' for example)
        """
        # List of values for expression
        values = []

        if to_bool(cfg_layer_login_filter['filterPrivate']):
            # If filter is private use user_login
            values.append(login)
        else:
            # Else use user groups
            values = list(groups)

        # Add all to values
        values.append('all')

        # Since LWC 3.8, we allow to have a list of groups (or logins)
        # separated by comma, with NO SPACES
        # only for PostgreSQL layers and if the option allow_multiple_acl_values
        # is set to True
        # For example the field can contain 'group_a,group_b,group_c'
        # To use only pure SQL allowed by QGIS, we can use LIKE items
        # For big dataset, a GIN index with pg_trgm must be used for the
        # filter field to improve performance
        # We cannot use array_remove, string_to_array or regexp_replace
        # as it should be SQL safe for QGIS Server

        value_filters = []

        # Quoted attribute with double-quotes
        quoted_field = QgsExpression.quotedColumnRef(cfg_layer_login_filter['filterAttribute'])

        # For each value (group, all, login, etc.), create a filter
        # combining all the possibility: equality & LIKE
        for value in values:
            filters = []
            # Quote the value with single quotes
            quoted_value = QgsExpression.quotedString(value)

            # equality
            filters.append(f'{quoted_field} = {quoted_value}')

            # Add LIKE statements to manage multiple values separated by comma
            if provider == 'postgres' and cfg_layer_login_filter.get('allow_multiple_acl_values'):
                # begins with value & comma
                quoted_like_value = QgsExpression.quotedString(f'{value},%')
                filters.append(f'{quoted_field} LIKE {quoted_like_value}')

                # ends with comma & value
                quoted_like_value = QgsExpression.quotedString(f'%,{value}')
                filters.append(f'{quoted_field} LIKE {quoted_like_value}')

                # value between two commas
                quoted_like_value = QgsExpression.quotedString(f'%,{value},%')
                filters.append(f'{quoted_field} LIKE {quoted_like_value}')

            # Build the filter for this value
            value_filters.append(' OR '.join(filters))

        # Build filter for all values
        layer_filter = ' OR '.join(value_filters)

        return layer_filter
