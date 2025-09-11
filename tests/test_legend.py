import logging

from .utils import _build_query_string, _check_request

from qgis.core import Qgis

from lizmap_server.get_legend_graphic import GetLegendGraphicFilter

LOGGER = logging.getLogger('server')

PROJECT = "legend.qgs"
PROJECT_INVALID = "legend_invalid.qgs"

BASE_QUERY = {
    'SERVICE': 'WMS',
    'REQUEST': 'GetLegendGraphic',
    'MAP': PROJECT,
    'FORMAT': 'APPLICATION/JSON',
}


def test_unique_symbol(client):
    """ Test unique symbol for layer. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'unique_symbol'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)
    #  {'nodes': [{'icon': 'ICON', 'title': 'unique_symbol', 'type': 'layer'}], 'title': ''}
    assert b['title'] == ''
    assert len(b['nodes']) == 1, b
    assert b['nodes'][0]['title'] == 'unique_symbol'
    assert b['nodes'][0].get('valid') is None
    assert 'icon' in b['nodes'][0]
    assert 'symbols' not in b['nodes'][0]


def test_categorized_symbol(client):
    """ Test categorized symbol for layer. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'categorized'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)
    assert b['nodes'][0]['title'] == 'categorized'
    assert b['nodes'][0].get('valid') is None
    assert 'icon' not in b['nodes'][0]
    assert 'symbols' in b['nodes'][0]

    symbols = b['nodes'][0]['symbols']
    # expected = {
    #     'nodes': [
    #         {
    #             'symbols': [
    #                 {'icon': 'ICON', 'title': 'Basse-Normandie', 'ruleKey': '0', 'checked': True, 'parentRuleKey': ''},
    #                 {'icon': 'ICON', 'title': 'Bretagne', 'ruleKey': '1', 'checked': True, 'parentRuleKey': ''},
    #                 {'icon': 'ICON', 'title': 'Centre', 'ruleKey': '2', 'checked': True, 'parentRuleKey': ''},
    #                 {'icon': 'ICON', 'title': 'Pays de la Loire', 'ruleKey': '3', 'checked': True, 'parentRuleKey': ''},
    #                 {'icon': 'ICON', 'title': '', 'ruleKey': '4', 'checked': True, 'parentRuleKey': ''}
    #             ],
    #             'title': 'categorized',
    #             'type': 'layer'
    #         }
    #     ],
    #     'title': ''
    # }
    assert len(symbols) == 5, symbols
    assert symbols[0]['title'] == 'Basse-Normandie', symbols[0]['title']
    assert symbols[0]['ruleKey'] == '0', symbols[0]['ruleKey']
    assert symbols[0]['checked']
    assert symbols[0]['parentRuleKey'] == ''
    assert b['title'] == ''
    assert b['nodes'][0]['title'] == 'categorized', b['nodes'][0]['title']


def test_simple_rule_based(client):
    """ Test rule based layer, simple conversion from categorized. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'rule_based'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)
    assert b['nodes'][0]['title'] == 'rule_based', b['nodes'][0]['title']
    assert 'icon' not in b['nodes'][0]
    assert 'symbols' in b['nodes'][0]
    assert b['nodes'][0].get('valid') is None

    symbols = b['nodes'][0]['symbols']

    assert len(symbols) == 5, symbols
    assert symbols[0]['title'] == 'Basse-Normandie', symbols[0]['title']
    assert symbols[0]['ruleKey'] == '{1e75ef9b-1c18-46c1-b7f7-b16efc5bb791}', symbols[0]['ruleKey']
    assert symbols[0]['checked']
    assert symbols[0]['parentRuleKey'] == '{9322759d-05f9-48ac-8947-3137d44d1832}', symbols[0]['parentRuleKey']
    assert 'scaleMaxDenom' not in symbols[0], symbols[0]['scaleMaxDenom']
    assert 'scaleMinDenom' not in symbols[0], symbols[0]['scaleMinDenom']
    expected = '"NAME_1" = \'Basse-Normandie\'' if Qgis.QGIS_VERSION_INT >= 32600 else ''
    assert symbols[0]['expression'] == expected, symbols[0]['expression']
    assert b['title'] == ''
    assert b['nodes'][0]['title'] == 'rule_based', b['nodes'][0]['title']


def test_categorized_symbol_feature_count(client):
    """ Test categorized symbol for layer. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'categorized'
    qs['SHOWFEATURECOUNT'] = 'True'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)
    assert b['nodes'][0]['title'].startswith('categorized'), b['nodes'][0]['title']
    assert 'icon' not in b['nodes'][0]
    assert 'symbols' in b['nodes'][0]
    assert b['nodes'][0].get('valid') is None

    symbols = b['nodes'][0]['symbols']
    # expected = {
    #     'nodes': [
    #         {
    #             'symbols': [
    #                 {'icon': 'ICON', 'title': 'Basse-Normandie', 'ruleKey': '0', 'checked': True, 'parentRuleKey': ''},
    #                 {'icon': 'ICON', 'title': 'Bretagne', 'ruleKey': '1', 'checked': True, 'parentRuleKey': ''},
    #                 {'icon': 'ICON', 'title': 'Centre', 'ruleKey': '2', 'checked': True, 'parentRuleKey': ''},
    #                 {'icon': 'ICON', 'title': 'Pays de la Loire', 'ruleKey': '3', 'checked': True, 'parentRuleKey': ''},
    #                 {'icon': 'ICON', 'title': '', 'ruleKey': '4', 'checked': True, 'parentRuleKey': ''}
    #             ],
    #             'title': 'categorized',
    #             'type': 'layer'
    #         }
    #     ],
    #     'title': ''
    # }
    assert len(symbols) == 5, symbols
    assert symbols[0]['title'] == 'Basse-Normandie [1]', symbols[0]['title']
    assert symbols[0]['ruleKey'] == '0', symbols[0]['ruleKey']
    assert symbols[0]['checked']
    assert symbols[0]['parentRuleKey'] == ''
    assert b['title'] == ''
    assert b['nodes'][0]['title'] == 'categorized [4]', b['nodes'][0]['title']


def test_simple_rule_based_feature_count(client):
    """ Test rule based layer, simple conversion from categorized. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'rule_based'
    qs['SHOWFEATURECOUNT'] = 'True'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)
    assert b['nodes'][0]['title'].startswith('rule_based'), b['nodes'][0]['title']
    assert 'icon' not in b['nodes'][0]
    assert 'symbols' in b['nodes'][0]
    assert b['nodes'][0].get('valid') is None

    symbols = b['nodes'][0]['symbols']

    assert len(symbols) == 5, symbols
    assert symbols[0]['title'] == 'Basse-Normandie [1]', symbols[0]['title']
    assert symbols[0]['ruleKey'] == '{1e75ef9b-1c18-46c1-b7f7-b16efc5bb791}', symbols[0]['ruleKey']
    assert symbols[0]['checked']
    assert symbols[0]['parentRuleKey'] == '{9322759d-05f9-48ac-8947-3137d44d1832}', symbols[0]['parentRuleKey']
    assert 'scaleMaxDenom' not in symbols[0], symbols[0]['scaleMaxDenom']
    assert 'scaleMinDenom' not in symbols[0], symbols[0]['scaleMinDenom']
    expected = '"NAME_1" = \'Basse-Normandie\'' if Qgis.QGIS_VERSION_INT >= 32600 else ''
    assert symbols[0]['expression'] == expected, symbols[0]['expression']
    assert b['title'] == ''
    assert b['nodes'][0]['title'] == 'rule_based [4]', b['nodes'][0]['title']


def test_valid_raster_layer(client):
    """ Test valid raster layer. """
    qs = dict(BASE_QUERY)
    qs['MAP'] = PROJECT
    qs['LAYER'] = 'raster'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)

    # Answer straight from QGIS Server
    if Qgis.QGIS_VERSION_INT < 33400:
        expected = {
            'nodes': [
                {
                    'symbols': [
                        {
                            'title': 'Band 1',
                        }, {
                            'title': '',
                        },
                    ],
                    'title': qs['LAYER'],
                    'type': 'layer',
                },
            ],
            'title': '',
        }
    else:
        expected = {
            'nodes': [
                {
                    'symbols': [
                        {
                            'title': 'Band 1',
                        }, {
                            # 'icon': '',
                            'max': 125,
                            'min': 50,
                            'title': '',
                        },
                    ],
                    'title': qs['LAYER'],
                    'type': 'layer',
                },
            ],
            'title': '',
        }
        del b['nodes'][0]['symbols'][1]['icon']

    assert b == expected, b


def test_invalid_layer_symbol_layer(client):
    """ Test unique symbol for layer. """
    qs = dict(BASE_QUERY)
    qs['MAP'] = PROJECT_INVALID
    qs['LAYER'] = 'unique_symbol'
    rv = client.get(_build_query_string(qs), PROJECT_INVALID)
    b = _check_request(rv)
    #  {'nodes': [{'icon': 'ICON', 'title': 'unique_symbol', 'type': 'layer'}], 'title': ''}
    assert b['title'] == ''
    assert len(b['nodes']) == 1, b
    assert b['nodes'][0]['title'] == 'unique_symbol'
    assert b['nodes'][0].get('valid') is False
    assert b['nodes'][0].get('icon') == GetLegendGraphicFilter.warning_icon()
    assert 'icon' in b['nodes'][0]
    assert 'symbols' not in b['nodes'][0]


def test_invalid_layer_raster_layer(client):
    """ Test invalid  raster layer. """
    qs = dict(BASE_QUERY)
    qs['MAP'] = PROJECT_INVALID
    qs['LAYER'] = 'raster'
    rv = client.get(_build_query_string(qs), PROJECT_INVALID)
    b = _check_request(rv)

    expected = {
        'title': '',
        'nodes': [
            {
                'type': 'layer',
                'title': qs['LAYER'],
                'icon': GetLegendGraphicFilter.warning_icon(),
                'valid': False,
            },
        ],
    }
    assert b == expected, b

    assert b['title'] == '', b
    assert len(b['nodes']) == 1, b
    assert b['nodes'][0]['title'] == qs['LAYER']
    assert b['nodes'][0].get('valid') is False
    assert b['nodes'][0].get('icon') == GetLegendGraphicFilter.warning_icon()
    assert 'icon' in b['nodes'][0]
    assert 'symbols' not in b['nodes'][0]


def test_invalid_layer_categorized_symbol_layer(client):
    """ Test categorized symbol for layer. """
    qs = dict(BASE_QUERY)
    qs['MAP'] = PROJECT_INVALID
    qs['LAYER'] = 'categorized'
    rv = client.get(_build_query_string(qs), PROJECT_INVALID)
    b = _check_request(rv)
    #  {'nodes': [{'icon': 'ICON', 'title': 'categorized', 'type': 'layer'}], 'title': ''}
    assert b['title'] == ''
    assert len(b['nodes']) == 1, b
    assert b['nodes'][0]['title'] == 'categorized'
    assert b['nodes'][0].get('valid') is False
    assert b['nodes'][0].get('icon') == GetLegendGraphicFilter.warning_icon()
    assert 'icon' in b['nodes'][0]
    assert 'symbols' not in b['nodes'][0]


def test_multiple_invalid_layers(client):
    """ Test multiple invalid layers. """
    qs = dict(BASE_QUERY)
    qs['MAP'] = PROJECT_INVALID
    qs['LAYER'] = 'unique_symbol,categorized'
    rv = client.get(_build_query_string(qs), PROJECT_INVALID)
    b = _check_request(rv)
    #  {'nodes': [{'icon': 'ICON', 'title': 'unique_symbol', 'type': 'layer'}], 'title': ''}
    assert len(b['nodes']) == 2, b
    assert b['title'] == ''
    assert b['nodes'][0]['title'] == 'categorized', b['nodes'][0]['title']
    assert b['nodes'][0].get('valid') is None
    # assert b['nodes'][0].get('icon') == GetLegendGraphicFilter.warning_icon()
    assert 'symbols' in b['nodes'][0]
    assert b['nodes'][1]['title'] == 'unique_symbol'
    assert b['nodes'][1].get('valid') is None
    # assert b['nodes'][1].get('icon') == GetLegendGraphicFilter.warning_icon()
    assert 'symbols' not in b['nodes'][1]


def test_invalid_layer_rule_based_symbol_layer(client):
    """ Test rule based layer, simple conversion from categorized. """
    qs = dict(BASE_QUERY)
    qs['MAP'] = PROJECT_INVALID
    qs['LAYER'] = 'rule_based'
    rv = client.get(_build_query_string(qs), PROJECT_INVALID)
    b = _check_request(rv)
    #  {'nodes': [{'icon': 'ICON', 'title': 'categorized', 'type': 'layer'}], 'title': ''}
    assert b['title'] == ''
    assert len(b['nodes']) == 1, b
    assert b['nodes'][0]['title'] == 'rule_based'
    assert b['nodes'][0].get('valid') is False
    assert b['nodes'][0].get('icon') == GetLegendGraphicFilter.warning_icon()
    assert 'icon' in b['nodes'][0]
    assert 'symbols' not in b['nodes'][0]


def test_invalid_layer_categorized_symbol_layer_feature_count(client):
    """ Test categorized symbol for layer with SHOW FEATURE COUNT. """
    qs = dict(BASE_QUERY)
    qs['MAP'] = PROJECT_INVALID
    qs['LAYER'] = 'categorized'
    qs['SHOWFEATURECOUNT'] = 'True'
    rv = client.get(_build_query_string(qs), PROJECT_INVALID)
    b = _check_request(rv)
    #  {'nodes': [{'icon': 'ICON', 'title': 'categorized', 'type': 'layer'}], 'title': ''}
    assert b['title'] == ''
    assert len(b['nodes']) == 1, b
    assert b['nodes'][0]['title'] == 'categorized'
    assert b['nodes'][0].get('valid') is False
    assert b['nodes'][0].get('icon') == GetLegendGraphicFilter.warning_icon()
    assert 'icon' in b['nodes'][0]
    assert 'symbols' not in b['nodes'][0]


def test_no_geom_layer(client):
    """ Test no geometry for layer. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'no_geom'
    rv = client.get(_build_query_string(qs), PROJECT)
    b = _check_request(rv)
    #  {'nodes': [], 'title': ''}
    assert b['title'] == ''
    assert len(b['nodes']) == 0, b
