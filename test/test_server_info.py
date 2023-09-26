import json
import os

from qgis.core import Qgis

__copyright__ = 'Copyright 2021, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

QUERY = "/lizmap/server.json"
KEY = 'QGIS_SERVER_LIZMAP_REVEAL_SETTINGS'


def test_lizmap_server_info(client):
    """Test the Lizmap API for server settings"""
    # The environment variable is already there
    assert os.getenv(KEY) == 'TRUE'

    # The query must work
    rv = client.get(QUERY)
    assert rv.status_code == 200

    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    json_content = json.loads(rv.content.decode('utf-8'))
    assert 'qgis_server' in json_content

    if 33000 <= Qgis.QGIS_VERSION_INT < 33200:
        assert json_content['qgis_server']['metadata']['name'] == "'s-Hertogenbosch"
    elif 32800 <= Qgis.QGIS_VERSION_INT < 32800:
        assert json_content['qgis_server']['metadata']['name'] == "Firenze"

    # Names and versions are used in Lizmap Web Client
    expected_plugins = ('atlasprint', 'wfsOutputExtension', 'lizmap_server')
    assert len(json_content['qgis_server']['plugins'].keys()) == len(expected_plugins)
    for plugin in expected_plugins:
        assert json_content['qgis_server']['plugins'][plugin]['name'] == plugin
        assert json_content['qgis_server']['plugins'][plugin]['version'] == 'not found'

    assert len(json_content['qgis_server']['fonts']) >= 1


def test_lizmap_server_info_env_check(client):
    """ Check the environment variable check. """
    # Remove the security environment variable, the query mustn't work
    del os.environ[KEY]
    rv = client.get(QUERY)
    assert rv.status_code == 400

    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    json_content = json.loads(rv.content.decode('utf-8'))
    assert [{'code': 'Bad request error', 'description': 'Invalid request'}] == json_content

    # Reset the environment variable just in case
    os.environ[KEY] = 'TRUE'
