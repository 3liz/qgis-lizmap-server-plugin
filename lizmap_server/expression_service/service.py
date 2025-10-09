#
# Expression service
#
from qgis.core import (
    QgsProject,
)
from qgis.server import (
    QgsRequestHandler,
    QgsServerInterface,
    QgsServerRequest,
    QgsServerResponse,
    QgsService,
)

from ..core import (
    get_lizmap_groups,
    get_lizmap_user_login,
)
from ..exception import ExpressionServiceError
from .. import logger

from .request_evaluate import evaluate
from .request_replaceexpressiontext import replace_expression_text
from .request_getfeaturewithformscope import get_feature_with_form_scope
from .request_virtualfields import virtual_fields


class ExpressionService(QgsService):
    def __init__(self, server_iface: QgsServerInterface) -> None:
        super().__init__()
        self.server_iface = server_iface

    def name(self) -> str:
        """Service name"""
        return "EXPRESSION"

    def version(self) -> str:
        """Service version"""
        return "1.0.0"

    def allowMethod(self, method: QgsServerRequest.Method) -> bool:
        """Check supported HTTP methods"""
        return method in (QgsServerRequest.GetMethod, QgsServerRequest.PostMethod)

    def executeRequest(
        self,
        request: QgsServerRequest,
        response: QgsServerResponse,
        project: QgsProject,
    ):
        """Execute a 'EXPRESSION' request"""
        if not self.allowMethod(request.method()):
            raise ExpressionServiceError("Method not allowed", "", 405)

        # Set lizmap variables
        request_handler = QgsRequestHandler(request, response)
        groups = get_lizmap_groups(request_handler)
        user_login = get_lizmap_user_login(request_handler)

        custom_var = project.customVariables()
        custom_var["lizmap_user"] = user_login
        custom_var["lizmap_user_groups"] = list(groups)  # QGIS can't store a tuple

        project.setCustomVariables(custom_var)

        params = request.parameters()

        try:
            reqparam = params.get("REQUEST", "").upper()

            if reqparam == "EVALUATE":
                evaluate(params, response, project)
            elif reqparam == "REPLACEEXPRESSIONTEXT":
                replace_expression_text(params, response, project, self.server_iface)
            elif reqparam == "GETFEATUREWITHFORMSCOPE":
                get_feature_with_form_scope(params, response, project)
            elif reqparam == "VIRTUALFIELDS":
                virtual_fields(params, response, project, self.server_iface)
            else:
                raise ExpressionServiceError(
                    "Bad request",
                    f"Invalid REQUEST parameter '{reqparam}'",
                    400,
                )
        except ExpressionServiceError as e:
            e.formatResponse(response)
        except Exception as e:
            logger.log_exception(e)
            err = ExpressionServiceError("Internal server error", "Internal 'lizmap' service error")
            err.formatResponse(response)
