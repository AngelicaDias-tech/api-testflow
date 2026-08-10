from app.engine.bruno_import import parse_bru

BRU_SAMPLE = """meta {
  name: Get User
  type: http
  seq: 1
}

get {
  url: https://api.exemplo.com/users/1?verbose=true
  body: none
  auth: bearer
}

headers {
  X-Custom: abc
}

auth:bearer {
  token: {{authToken}}
}
"""


def test_parse_bru_single_request():
    result = parse_bru(BRU_SAMPLE)
    assert result["method"] == "GET"
    assert result["url"] == "https://api.exemplo.com/users/1"
    assert result["query_params"] == {"verbose": "true"}
    assert result["headers"] == {"X-Custom": "abc"}
    assert result["auth"]["type"] == "bearer"
    assert "authToken" in result["unresolved_variables"]


def test_parse_bru_with_json_body():
    bru = """meta {
  name: Create User
}

post {
  url: https://api.exemplo.com/users
  body: json
  auth: none
}

body:json {
  {
    "name": "Ana"
  }
}
"""
    result = parse_bru(bru)
    assert result["method"] == "POST"
    assert result["body_type"] == "json"
    assert '"name"' in result["body"]
