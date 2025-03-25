import io
import json
import xml.etree.ElementTree as ET

from typing import Dict, Union

import lxml.etree

from PIL import Image
from qgis.server import QgsBufferServerResponse
from urllib.parse import urlencode

__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

NAMESPACES = {
    'xlink': "http://www.w3.org/1999/xlink",
    'wms': "http://www.opengis.net/wms",
    'wfs': "http://www.opengis.net/wfs",
    'wcs': "http://www.opengis.net/wcs",
    'ows': "http://www.opengis.net/ows/1.1",
    'gml': "http://www.opengis.net/gml",
    'xsi': "http://www.w3.org/2001/XMLSchema-instance",
}

PROJECT_FILE = "france_parts.qgs"

BASE = {
    "MAP": PROJECT_FILE,
}


class OWSResponse:

    def __init__(self, resp: QgsBufferServerResponse) -> None:
        self._resp = resp
        self._xml = None

    @property
    def xml(self) -> 'xml':
        if self._xml is None and self._resp.headers().get('Content-Type', '').find('text/xml') == 0:
            self._xml = lxml.etree.fromstring(self.content)
        return self._xml

    @property
    def content(self) -> bytes:
        return bytes(self._resp.body())

    @property
    def status_code(self) -> int:
        return self._resp.statusCode()

    @property
    def headers(self) -> Dict[str, str]:
        return self._resp.headers()

    def xpath(self, path: str) -> lxml.etree.Element:
        assert self.xml is not None
        return self.xml.xpath(path, namespaces=NAMESPACES)

    def xpath_text(self, path: str) -> str:
        assert self.xml is not None
        return ' '.join(e.text for e in self.xpath(path))


def _build_query_string(params: dict, use_urllib: bool = False) -> str:
    """ Build a query parameter from a dictionary. """
    if use_urllib:
        return "?" + urlencode(params)

    query_string = '?'
    for k, v in params.items():
        query_string += f'{k}={v}&'
    return query_string


def _check_request(
        result: OWSResponse, content_type: str = 'application/json', http_code: int = 200,
) -> Union[dict, ET.Element, Image.Image]:
    """ Check the output and return the content. """
    assert result.status_code == http_code, f'HTTP code {result.status_code}, expected {http_code}'
    assert result.headers.get('Content-Type', '').lower().find(content_type) == 0, f'Headers {result.headers}'

    if content_type in ('application/json', 'application/vnd.geo+json', 'text/xml'):
        content = result.content.decode('utf-8')

        if content_type in ('application/json', 'application/vnd.geo+json'):
            return json.loads(content)
        else:
            return ET.fromstring(content)

    if content_type in ('image/png', ):
        return Image.open(io.BytesIO(result.content))
