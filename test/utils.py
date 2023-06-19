import json

__copyright__ = 'Copyright 2023, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'


def _build_query_string(params: dict) -> str:
    """ Build a query parameter from a dictionary. """
    query_string = '?'
    for k, v in params.items():
        query_string += f'{k}={v}&'
    return query_string


def _check_request(result, content_type: str = 'application/json', http_code=200) -> dict:
    """ Check the output and return the content. """
    assert result.status_code == http_code, f'HTTP code {result.status_code}, expected {http_code}'
    assert result.headers.get('Content-Type', '').lower().find(content_type) == 0, f'Headers {result.headers}'
    return json.loads(result.content.decode('utf-8'))
