from app.engine.discovery import discover_checks

CTX = {
    "status_code": 200,
    "content_type": "application/json; charset=utf-8",
    "json_valid": True,
    "response_time_ms": 80.0,
    "body_json": {"id": 123, "name": "João", "status": "ACTIVE", "email": "joao@email.com"},
}


def test_discover_generates_expected_technical_checks():
    checks = discover_checks(CTX)
    fields_ops = {(c["field"], c["operator"]) for c in checks}

    assert ("id", "exists") in fields_ops
    assert ("id", "type_is") in fields_ops
    assert ("email", "is_email_format") in fields_ops
    assert ("$.status_code", "equals") in fields_ops
    assert (None, "is_valid_json") in fields_ops

    # NUNCA deve inferir automaticamente um valor de negocio (secao 9):
    # nao pode existir um check auto que afirme status == "ACTIVE".
    for c in checks:
        if c["field"] == "status":
            assert c["operator"] in ("exists", "type_is"), (
                "descoberta automatica nao pode assumir valor de negocio para 'status'"
            )


def test_all_discovered_checks_are_marked_auto():
    checks = discover_checks(CTX)
    assert all(c["source"] == "auto" for c in checks)
