from app.ai.technical_rule_parser import build_technical_rule, is_technical_line, parse_technical_line

KNOWN_FIELDS = ["private", "stargazers_count", "forks_count", "name", "full_name"]


def test_is_technical_line_detects_operators():
    assert is_technical_line("stargazers_count > 100")
    assert is_technical_line("private == false")
    assert is_technical_line("forks_count >= 10")
    assert is_technical_line('name == "Hello-World"')
    assert not is_technical_line("Quero garantir que o repositório não seja privado.")


def test_teste_7_greater_than_technical_syntax():
    parsed = parse_technical_line("stargazers_count > 100", KNOWN_FIELDS)
    assert parsed == {"field": "stargazers_count", "operator": "greater_than", "expected": 100}


def test_teste_8_greater_than_or_equal_technical_syntax():
    parsed = parse_technical_line("forks_count >= 10", KNOWN_FIELDS)
    assert parsed == {"field": "forks_count", "operator": "greater_than_or_equal", "expected": 10}


def test_equals_boolean_technical_syntax():
    parsed = parse_technical_line("private == false", KNOWN_FIELDS)
    assert parsed == {"field": "private", "operator": "equals", "expected": False}


def test_equals_quoted_string_technical_syntax():
    parsed = parse_technical_line('name == "Hello-World"', KNOWN_FIELDS)
    assert parsed == {"field": "name", "operator": "equals", "expected": "Hello-World"}


def test_technical_syntax_does_not_invent_field():
    parsed = parse_technical_line("customerType == PREMIUM", KNOWN_FIELDS)
    assert parsed == {"unresolved": True, "candidate": "customerType"}


def test_technical_syntax_without_known_fields_still_parses():
    # Antes do primeiro "Testar API" (sem known_fields ainda), a sintaxe
    # técnica continua reconhecível - so nao ha como validar contra a
    # resposta real ainda.
    parsed = parse_technical_line("stargazers_count > 100", [])
    assert parsed == {"field": "stargazers_count", "operator": "greater_than", "expected": 100}


def test_build_technical_rule_shape_matches_ai_rules():
    parsed = parse_technical_line("stargazers_count > 100", KNOWN_FIELDS)
    rule = build_technical_rule(parsed, "stargazers_count > 100")
    assert rule["field"] == "stargazers_count"
    assert rule["operator"] == "greater_than"
    assert rule["expected"] == 100
    assert rule["source"] == "custom"
    assert "id" in rule and "description" in rule
