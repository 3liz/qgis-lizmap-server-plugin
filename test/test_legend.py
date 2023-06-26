import logging

from test.utils import _build_query_string, _check_request

LOGGER = logging.getLogger('server')

__copyright__ = 'Copyright 2023, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

PROJECT = "legend.qgs"

BASE_QUERY = {
    'SERVICE': 'WMS',
    'REQUEST': 'GetLegendGraphic',
    'MAP': PROJECT,
    'FORMAT': 'APPLICATION/JSON',
}


def test_unique_symbole(client):
    """ Test unique symbol for layer. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'unique_symbol'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)
    #  {'nodes': [{'icon': 'ICON', 'title': 'unique_symbol', 'type': 'layer'}], 'title': ''}
    assert b['title'] == ''
    assert len(b['nodes']) == 1, b


def test_categorized_symbole(client):
    """ Test categorized symbol for layer. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'categorized'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)
    symbols = b['nodes'][0]['symbols']
    # expected = {
    #     'nodes': [
    #         {
    #             'symbols': [
    #                 {'icon': 'ICON', 'title': 'Basse-Normandie', 'ruleKey': '0', 'checked': True},
    #                 {'icon': 'ICON', 'title': 'Bretagne', 'ruleKey': '1', 'checked': True},
    #                 {'icon': 'ICON', 'title': 'Centre', 'ruleKey': '2', 'checked': True},
    #                 {'icon': 'ICON', 'title': 'Pays de la Loire', 'ruleKey': '3', 'checked': True},
    #                 {'icon': 'ICON', 'title': '', 'ruleKey': '4', 'checked': True}
    #             ],
    #             'title': 'categorized',
    #             'type': 'layer'
    #         }
    #     ],
    #     'title': ''
    # }
    assert len(symbols) == 5, symbols
    assert symbols[0]['title'] == 'Basse-Normandie'
    assert symbols[0]['ruleKey'] == '0'
    assert symbols[0]['checked']
    assert b['title'] == ''
    assert b['nodes'][0]['title'] == 'categorized'


def test_simple_rule_based(client):
    """ Test rule based layer, simple conversion from categorized. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'rule_based'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)
    symbols = b['nodes'][0]['symbols']

    assert len(symbols) == 5, symbols
    assert symbols[0]['title'] == 'Basse-Normandie'
    assert symbols[0]['ruleKey'] == '{1e75ef9b-1c18-46c1-b7f7-b16efc5bb791}', symbols[0]['ruleKey']
    assert symbols[0]['checked']
    assert b['title'] == ''
    assert b['nodes'][0]['title'] == 'rule_based', b['nodes'][0]['title']
