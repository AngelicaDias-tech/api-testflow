from app.engine.evaluator import evaluate_check

CTX = {
    "status_code": 200,
    "content_type": "application/json; charset=utf-8",
    "json_valid": True,
    "response_time_ms": 120.5,
    "body_json": {"id": 123, "name": "João", "status": "INACTIVE", "email": "joao@email.com", "tags": ["a", "b"]},
}


def test_equals_pass():
    r = evaluate_check({"field": "id", "operator": "equals", "expected": "123"}, CTX)
    assert r.passed


def test_equals_fail_expected_vs_actual():
    r = evaluate_check({"field": "status", "operator": "equals", "expected": "ACTIVE"}, CTX)
    assert not r.passed
    assert r.actual == "INACTIVE"
    assert r.expected == "ACTIVE"


def test_type_is_integer():
    r = evaluate_check({"field": "id", "operator": "type_is", "expected": "integer"}, CTX)
    assert r.passed


def test_exists_and_not_exists():
    assert evaluate_check({"field": "name", "operator": "exists", "expected": None}, CTX).passed
    assert evaluate_check({"field": "nope", "operator": "not_exists", "expected": None}, CTX).passed


def test_is_email_format():
    assert evaluate_check({"field": "email", "operator": "is_email_format", "expected": None}, CTX).passed


def test_contains_on_list():
    assert evaluate_check({"field": "tags", "operator": "contains", "expected": "a"}, CTX).passed


def test_greater_than():
    assert evaluate_check({"field": "id", "operator": "greater_than", "expected": "100"}, CTX).passed
    assert not evaluate_check({"field": "id", "operator": "greater_than", "expected": "200"}, CTX).passed


def test_missing_field():
    r = evaluate_check({"field": "does.not.exist", "operator": "equals", "expected": "x"}, CTX)
    assert not r.passed


def test_status_code_and_response_time():
    assert evaluate_check({"field": "$.status_code", "operator": "equals", "expected": "200"}, CTX).passed
    assert evaluate_check(
        {"field": "$.response_time_ms", "operator": "less_than", "expected": "500"}, CTX
    ).passed


# --- regras condicionais sobre arrays (ex: "clientes PREMIUM devem estar ativos") ---

CTX_CUSTOMERS = {
    "status_code": 200,
    "content_type": "application/json; charset=utf-8",
    "json_valid": True,
    "response_time_ms": 90.0,
    "body_json": {
        "customers": [
            {"id": 1, "tier": "PREMIUM", "active": True, "limit": 5000},
            {"id": 2, "tier": "PREMIUM", "active": True, "limit": 200},  # viola limit > 1000
            {"id": 3, "tier": "BASIC", "active": False, "limit": 50},
        ]
    },
}


def test_array_condition_all_match_passes():
    check = {
        "field": "active",
        "operator": "equals",
        "expected": "True",
        "array_path": "customers",
        "condition_field": "tier",
        "condition_operator": "equals",
        "condition_expected": "PREMIUM",
    }
    r = evaluate_check(check, CTX_CUSTOMERS)
    assert r.passed
    assert "2/2" in r.actual


def test_array_condition_detects_violation_with_expected_vs_actual():
    check = {
        "field": "limit",
        "operator": "greater_than",
        "expected": "1000",
        "array_path": "customers",
        "condition_field": "tier",
        "condition_operator": "equals",
        "condition_expected": "PREMIUM",
    }
    r = evaluate_check(check, CTX_CUSTOMERS)
    assert not r.passed
    assert "item[1]" in r.actual
    assert "200" in r.actual


def test_array_condition_no_matches_is_skipped_not_passed_or_failed():
    check = {
        "field": "active",
        "operator": "equals",
        "expected": "True",
        "array_path": "customers",
        "condition_field": "tier",
        "condition_operator": "equals",
        "condition_expected": "GOLD",  # nenhum cliente e GOLD nesta resposta
    }
    r = evaluate_check(check, CTX_CUSTOMERS)
    assert r.skipped
    assert "0/3" in r.actual
    assert "não satisfeita" in r.message
    assert "SKIPPED" in r.message


def test_array_condition_missing_array_fails_clearly():
    check = {
        "field": "active",
        "operator": "equals",
        "expected": "True",
        "array_path": "does_not_exist",
        "condition_field": "tier",
        "condition_operator": "equals",
        "condition_expected": "PREMIUM",
    }
    r = evaluate_check(check, CTX_CUSTOMERS)
    assert not r.passed


def test_array_root_is_the_list():
    ctx = {**CTX_CUSTOMERS, "body_json": CTX_CUSTOMERS["body_json"]["customers"]}
    check = {
        "field": "active",
        "operator": "equals",
        "expected": "True",
        "array_path": "",
        "condition_field": "tier",
        "condition_operator": "equals",
        "condition_expected": "PREMIUM",
    }
    r = evaluate_check(check, ctx)
    assert r.passed


# --- regra condicional sobre resposta PLANA (sem array) ---
# ex: "Se o repositorio for publico, garanta mais de 100 estrelas"

CTX_FLAT_REPO = {
    "status_code": 200,
    "content_type": "application/json",
    "json_valid": True,
    "response_time_ms": 80.0,
    "body_json": {"name": "Hello-World", "private": False, "stargazers_count": 3755, "forks_count": 120},
}


def test_flat_condition_passes_when_condition_and_rule_hold():
    check = {
        "field": "stargazers_count",
        "operator": "greater_than",
        "expected": "100",
        "array_path": "",
        "condition_field": "private",
        "condition_operator": "equals",
        "condition_expected": "False",
    }
    r = evaluate_check(check, CTX_FLAT_REPO)
    assert r.passed


def test_flat_condition_fails_when_rule_violated():
    check = {
        "field": "stargazers_count",
        "operator": "greater_than",
        "expected": "1000000",
        "array_path": "",
        "condition_field": "private",
        "condition_operator": "equals",
        "condition_expected": "False",
    }
    r = evaluate_check(check, CTX_FLAT_REPO)
    assert not r.passed


def test_flat_condition_false_is_skipped_not_passed_or_failed():
    # o repositorio E privado nesta resposta - a condicao "private == True"
    # nao bate, entao a regra de estrelas nem chega a ser avaliada: nem
    # PASS nem FAIL, e SKIPPED (secao 7 do pedido que introduziu isso).
    check = {
        "field": "stargazers_count",
        "operator": "greater_than",
        "expected": "1000000",
        "array_path": "",
        "condition_field": "private",
        "condition_operator": "equals",
        "condition_expected": "True",
    }
    r = evaluate_check(check, CTX_FLAT_REPO)
    assert r.skipped
    assert "não satisfeita" in r.message
