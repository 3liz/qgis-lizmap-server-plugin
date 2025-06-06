__copyright__ = 'Copyright 2021, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import configparser
import os

from pathlib import Path
from typing import Union

from qgis.core import Qgis, QgsMessageLog

"""
Tools for Lizmap.
"""


def to_bool(val: Union[str, int, float, bool, None]) -> bool:
    """ Convert lizmap config value to boolean """
    if isinstance(val, str):
        # For string, compare lower value to True string
        return val.lower() in ('yes', 'true', 't', '1')
    else:
        return bool(val)


def version() -> str:
    """ Returns the Lizmap current version. """
    file_path = Path(__file__).parent.joinpath('metadata.txt')
    config = configparser.ConfigParser()
    try:
        config.read(file_path, encoding='utf8')
    except UnicodeDecodeError:
        # Issue LWC https://github.com/3liz/lizmap-web-client/issues/1908
        # Maybe a locale issue ?
        # Do not use logger here, circular import
        # noinspection PyTypeChecker
        QgsMessageLog.logMessage(
            "Error, an UnicodeDecodeError occurred while reading the metadata.txt. Is the locale "
            "correctly set on the server ?",
            "Lizmap", Qgis.MessageLevel.Critical)
        return 'NULL'
    else:
        return config["general"]["version"]


def check_environment_variable() -> bool:
    """ Check the server configuration. """
    if not to_bool(os.environ.get('QGIS_SERVER_LIZMAP_REVEAL_SETTINGS', '')):
        QgsMessageLog.logMessage(
            'The Lizmap API is currently not enabled. Please read the documentation how to enable the Lizmap API '
            'on QGIS server side '
            'https://docs.lizmap.com/current/en/install/pre_requirements.html#lizmap-server-plugin '
            'An environment variable must be enabled to have Lizmap Web Client ≥ 3.5 working.',
            "Lizmap",
            Qgis.MessageLevel.Critical,
        )
        return False

    return True
