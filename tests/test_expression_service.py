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
