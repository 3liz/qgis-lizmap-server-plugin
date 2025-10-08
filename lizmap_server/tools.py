import configparser
import functools
import os

from importlib import resources
from pathlib import Path
from typing import Union, cast


from . import logger

"""
Tools for Lizmap.
"""


PACKAGE_NAME = "lizmap_server"


def to_bool(val: Union[str, int, float, bool, None]) -> bool:
    """ Convert lizmap config value to boolean """
    # For string, compare lower value to True string
    return val.lower() in ('yes', 'true', 'y', 't', '1') if isinstance(val, str) else bool(val)


def plugin_path(*args: Union[str, Path]) -> Path:
    """Returns the path to the plugin resources"""
    return cast("Path", resources.files(PACKAGE_NAME)).joinpath(*args)


@functools.cache
def plugin_metadata() -> configparser.ConfigParser:
    """Parse plugin metadata"""
    path = plugin_path("metadata.txt")
    config = configparser.ConfigParser()
    config.read(path, encoding="utf8")
    return config


def version() -> str:
    """ Returns the Lizmap current version. """
    return plugin_metadata()["general"]["version"]


def check_environment_variable() -> bool:
    """ Check the server configuration. """
    lizmap_enabled = to_bool(os.environ.get('QGIS_SERVER_LIZMAP_REVEAL_SETTINGS', ''))
    if not lizmap_enabled:
        logger.critical(
            "The Lizmap API is currently not enabled. Please read the documentation "
            "how to enable the Lizmap API on QGIS server side "
            "'https://docs.lizmap.com/current/en/install/pre_requirements.html"
            "#lizmap-server-plugin' "
            "An environment variable must be enabled to have Lizmap Web "
            "Client ≥ 3.5 working.",
        )

    return lizmap_enabled
