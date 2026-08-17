"""Substituicao de {{variavel}} (compartilhada por Cenarios de Teste e
Massas de teste via CSV) - ver app/engine/templating.py."""

from __future__ import annotations

from app.engine.templating import find_placeholders, render_checks, render_request_def, render_template


def test_render_template_substitui_variaveis_conhecidas():
    assert render_template('{"cpf": "{{cpf}}", "idade": {{idade}}}', {"cpf": "12345678900", "idade": 30}) == (
        '{"cpf": "12345678900", "idade": 30}'
    )


def test_render_template_preserva_placeholder_sem_valor_correspondente():
    assert render_template("{{cpf}} e {{outro}}", {"cpf": "123"}) == "123 e {{outro}}"


def test_render_template_none_passa_direto():
    assert render_template(None, {"cpf": "123"}) is None


def test_render_template_booleano_vira_true_false_minusculo():
    assert render_template("{{ativo}}", {"ativo": True}) == "true"
    assert render_template("{{ativo}}", {"ativo": False}) == "false"


def test_find_placeholders():
    assert find_placeholders('{"cpf": "{{cpf}}", "valor": {{valor}}}') == {"cpf", "valor"}
    assert find_placeholders("sem variaveis") == set()


def test_render_request_def_nao_muta_original_e_resolve_body_url_headers_query():
    original = {
        "method": "POST",
        "url": "https://api.exemplo.com/clientes/{{cpf}}",
        "headers": {"X-Trace": "{{cpf}}"},
        "query_params": {"origem": "{{origem}}"},
        "body": '{"cpf": "{{cpf}}", "idade": {{idade}}}',
        "body_type": "json",
        "auth": {"type": "none"},
    }
    resolved = render_request_def(original, {"cpf": "12345678900", "idade": 30, "origem": "app"})

    assert resolved["url"] == "https://api.exemplo.com/clientes/12345678900"
    assert resolved["headers"]["X-Trace"] == "12345678900"
    assert resolved["query_params"]["origem"] == "app"
    assert resolved["body"] == '{"cpf": "12345678900", "idade": 30}'
    # original intocado — um cenario/massa nunca altera a ApiRequestDef salva
    assert original["url"] == "https://api.exemplo.com/clientes/{{cpf}}"
    assert original["body"] == '{"cpf": "{{cpf}}", "idade": {{idade}}}'


def test_render_checks_resolve_expected_com_placeholder_mas_preserva_regras_normais():
    checks = [
        {"field": "status", "operator": "equals", "expected": "{{resultado_esperado}}"},
        {"field": "id", "operator": "greater_than", "expected": 0},
    ]
    resolved = render_checks(checks, {"resultado_esperado": "aprovado"})

    assert resolved[0]["expected"] == "aprovado"
    assert resolved[1]["expected"] == 0  # sem placeholder, valor original preservado
    # input nao mutado
    assert checks[0]["expected"] == "{{resultado_esperado}}"


def test_render_checks_condition_expected_tambem_e_resolvido():
    checks = [
        {
            "field": "active",
            "operator": "equals",
            "expected": True,
            "array_path": "customers",
            "condition_field": "tier",
            "condition_operator": "equals",
            "condition_expected": "{{tier}}",
        }
    ]
    resolved = render_checks(checks, {"tier": "PREMIUM"})
    assert resolved[0]["condition_expected"] == "PREMIUM"
