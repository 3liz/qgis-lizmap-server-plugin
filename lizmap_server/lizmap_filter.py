from qgis.core import QgsProject
from qgis.server import QgsServerFilter, QgsServerInterface

from .core import get_lizmap_config, get_lizmap_groups
from .exception import LizmapFilterException
from .request_expressions import forbidden_function_in_request
from .tools import unwrap
from . import logger


class LizmapFilter(QgsServerFilter):
    def __init__(self, server_iface: QgsServerInterface) -> None:
        logger.info("LizmapFilter.init")
        super().__init__(server_iface)

        self.iface = server_iface

    def requestReady(self):
        """Check the request before QGIS Server handles it.

        The expressions of the request are checked for every user, then the
        access to the project is checked with the Lizmap user groups.
        """
        # noinspection PyBroadException
        try:
            # Check the expressions sent in the request, even for an anonymous user
            if not self._check_request_expressions():
                return

            # Check first the headers to avoid unnecessary config file reading
            # Get Lizmap user groups defined in request headers
            groups = get_lizmap_groups(unwrap(self.iface.requestHandler()))

            # If groups is empty, no Lizmap user groups provided by the request.
            # The request can be evaluated by QGIS Server
            if len(groups) == 0:
                return

            # Get Lizmap config
            cfg = get_lizmap_config(self.iface.configFilePath())
            if not cfg:
                # Lizmap config is empty
                logger.warning("Lizmap config is empty")
                # The request can be evaluated by QGIS Server
                return

            cfg_options = cfg.get("options")
            # Check Lizmap config options
            if not cfg_options:
                # Lizmap config has no options
                logger.warning("Lizmap config has no options")
                # The request can be evaluated by QGIS Server
                return

            cfg_acl = cfg_options.get("acl")

            # Check project acl option
            if not cfg_acl:
                # No acl defined
                logger.info("No acl defined in Lizmap config")
                # The request can be evaluated by QGIS Server
                return

            # Get project acl option
            logger.info("Acl defined in Lizmap config")

            # If one Lizmap user group provided in request headers is
            # defined in project acl option, the request can be evaluated
            # by QGIS Server
            for group in groups:
                if group in cfg_acl:
                    return

            # The lizmap user groups provided in request header are not
            # authorized to get access to the QGIS Project
            exc = LizmapFilterException("Forbidden", "No ACL permissions", response_code=403)

            # Get request handler
            handler = unwrap(self.iface.requestHandler())
            # use setServiceException to be sure to stop the request
            handler.setServiceException(exc)

        except Exception as e:
            logger.log_exception(e)

    def _check_request_expressions(self) -> bool:
        """Reject the request if one of its expressions calls a forbidden function.

        :returns: True if the request can go on, False if it has been rejected.
        """
        handler = unwrap(self.iface.requestHandler())

        # The body, e.g. a WFS GetFeature or Transaction XML document
        body = ""
        if hasattr(handler, "data"):
            data = handler.data()
            if data:
                body = bytes(data).decode("utf-8", errors="replace")

        name = forbidden_function_in_request(dict(handler.parameterMap()), body)
        if name is None:
            return True

        # use setServiceException to be sure to stop the request
        logger.warning(f"Request rejected: the expression function '{name}' is not allowed")
        exc = LizmapFilterException(
            "InvalidParameterValue",
            f"Expression function '{name}' is not allowed",
            response_code=400,
        )
        handler.setServiceException(exc)
        return False

    def responseComplete(self):
        # Remove lizmap variables for expression
        project = unwrap(QgsProject.instance())
        custom_var = project.customVariables()
        custom_var.pop("lizmap_user", None)
        custom_var.pop("lizmap_user_groups", None)
        # NOTE: wrong type annotations in QGIS 4
        project.setCustomVariables(custom_var)  # ty: ignore[invalid-argument-type]
