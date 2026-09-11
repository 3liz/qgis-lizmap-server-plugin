"""Tests Expression service"""

import json
from urllib.parse import quote

import pytest

from tests.utils import _build_query_string, _check_request


def test_request_unknown(client):
    """Test Expression service with an unknown request"""
    projectfile = "france_parts.qgs"

    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "UNKNOWN_REQUEST",
        "MAP": "france_parts.qgs",
    }
    rv = client.get(_build_query_string(qs), projectfile)
    b = _check_request(rv, http_code=400)

    assert "status" in b
    assert b["status"] == "fail"

    assert "code" in b
    assert "message" in b


#
# The EXPRESSION service evaluates unrestricted client expressions
#
# The fix is design-level: either allowlist the referenced functions and layers
# on the unsafe paths, or gate them behind an environment variable. The tests
# only assert the outcome — the disclosed value must not reach the response —
# so any of those remediations satisfies them.
#


SECRET_ENV = "LIZMAP_TEST_DATABASE_PASSWORD"
SECRET_VALUE = "s3cr3t-database-password"

EXPRESSION_PROJECT = "france_parts.qgs"
LAYER = "france_parts"


@pytest.fixture
def secret_env(monkeypatch):
    """An environment variable holding a secret, as a database password would."""
    monkeypatch.setenv(SECRET_ENV, SECRET_VALUE)
    return SECRET_VALUE


ENV_REQUESTS = {
    "EVALUATE": {
        "REQUEST": "Evaluate",
        "EXPRESSIONS": '{{"a":"{}"}}'.format(quote(f"env('{SECRET_ENV}')", safe="")),
    },
    "VIRTUALFIELDS": {
        "REQUEST": "VirtualFields",
        "VIRTUALS": '{{"a":"{}"}}'.format(quote(f"env('{SECRET_ENV}')", safe="")),
        "LIMIT": "1",
    },
    "REPLACEEXPRESSIONTEXT": {
        "REQUEST": "ReplaceExpressionText",
        "STRING": quote(f"[% env('{SECRET_ENV}') %]", safe=""),
    },
}


@pytest.mark.parametrize("request_name", sorted(ENV_REQUESTS))
def test_security_4_env_is_not_disclosed(client, secret_env, request_name):
    """`env()` must not read the server environment on behalf of a client."""
    qs = {
        "SERVICE": "EXPRESSION",
        "MAP": EXPRESSION_PROJECT,
        "LAYER": LAYER,
    }
    qs.update(ENV_REQUESTS[request_name])

    response = client.get(_build_query_string(qs), EXPRESSION_PROJECT)

    assert response.status_code == 400
    assert SECRET_VALUE.encode() not in response.content, response.content


def test_security_4_env_is_not_an_oracle_in_a_filter(client, secret_env):
    """A FILTER must not be usable to guess the value of an environment variable."""
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "GetFeatureWithFormScope",
        "MAP": EXPRESSION_PROJECT,
        "LAYER": LAYER,
        "FORM_FEATURE": '{"type":"Feature","geometry":null,"properties":{"prop0":"x"}}',
    }

    def _features(value):
        query = dict(qs)
        query["FILTER"] = quote(f"env('{SECRET_ENV}') = '{value}'", safe="")
        response = client.get(_build_query_string(query), EXPRESSION_PROJECT)
        assert response.status_code == 400
        content = json.loads(response.content.decode("utf-8"))
        return len(content.get("features", []))

    # A right and a wrong guess must not be distinguishable
    assert _features(SECRET_VALUE) == _features("wrong-guess")


# NOTE: aggregations fonctions bypass access control restrictions
# EXPRESSION based services must *NOT* be exposed if access control
# restrictions apply
@pytest.mark.xfail
def test_security_4_aggregate_does_not_bypass_the_login_filter(client):
    """`aggregate()` must not read the rows hidden by the login filter.

    The 'france_parts_liz_filter_group' project filters the layer on 'NAME_1'
    against the user groups: the 'test1' group sees no feature at all.
    """
    project_file = "france_parts_liz_filter_group.qgs"
    expression = "aggregate('france_parts','concatenate',attribute('NAME_1'),concatenator:=',')"
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": project_file,
        "LAYER": LAYER,
        "EXPRESSIONS": '{{"a":"{}"}}'.format(quote(expression, safe="")),
    }

    response = client.get(
        _build_query_string(qs),
        project_file,
        {"X-Lizmap-User-Groups": "test1"},
    )

    assert response.status_code == 400
    assert b"Bretagne" not in response.content, response.content
    assert b"Pays de la Loire" not in response.content, response.content
