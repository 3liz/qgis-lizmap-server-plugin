import io
import json
import xml.etree.ElementTree as ET

from PIL import Image

__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'


def _build_query_string(params: dict) -> str:
    """ Build a query parameter from a dictionary. """
    query_string = '?'
    for k, v in params.items():
        query_string += f'{k}={v}&'
    return query_string


def _check_request(result, content_type: str = 'application/json', http_code=200):
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
