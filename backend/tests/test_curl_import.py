from app.engine.curl_import import parse_curl


def test_parse_simple_get_with_bearer():
    curl = """curl --location 'https://api.exemplo.com/clientes/123' \\
--header 'Authorization: Bearer TOKEN123' \\
--header 'Content-Type: application/json'"""
    result = parse_curl(curl)
    assert result["method"] == "GET"
    assert result["url"] == "https://api.exemplo.com/clientes/123"
    assert result["auth"] == {"type": "bearer", "token": "TOKEN123"}
    assert result["headers"]["Content-Type"] == "application/json"


def test_parse_post_with_json_body():
    curl = (
        "curl -X POST https://api.exemplo.com/clientes "
        "-H 'Content-Type: application/json' -d '{\"name\": \"Ana\"}'"
    )
    result = parse_curl(curl)
    assert result["method"] == "POST"
    assert result["body_type"] == "json"
    assert '"name"' in result["body"]


def test_parse_query_params():
    curl = "curl 'https://api.exemplo.com/busca?page=1&limit=10'"
    result = parse_curl(curl)
    assert result["query_params"] == {"page": "1", "limit": "10"}
    assert result["url"] == "https://api.exemplo.com/busca"


def test_parse_basic_auth():
    curl = "curl -u user:pass https://api.exemplo.com/protegido"
    result = parse_curl(curl)
    assert result["auth"] == {"type": "basic", "username": "user", "password": "pass"}
