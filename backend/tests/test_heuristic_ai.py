from app.ai.heuristic_provider import HeuristicAIProvider
from app.ai.technical_rule_parser import parse_multiple_lines

provider = HeuristicAIProvider()


def test_nl_to_rules_basic_example_from_spec():
    text = "Quero garantir que o status seja ACTIVE e que o id seja um número."
    result = provider.nl_to_rules(text, None)
    rules = result["rules"]
    assert len(rules) == 2

    status_rule = next(r for r in rules if r["field"] == "status")
    assert status_rule["operator"] == "equals"
    assert status_rule["expected"] == "ACTIVE"

    id_rule = next(r for r in rules if r["field"] == "id")
    assert id_rule["operator"] == "type_is"
    assert id_rule["expected"] == "number"


def test_nl_to_rules_never_marks_as_auto():
    result = provider.nl_to_rules("o campo status seja ACTIVE", None)
    assert all(r["source"] == "ai_suggested" for r in result["rules"])


def test_negative_cases_mark_mutating_as_requiring_confirmation():
    cases = provider.suggest_negative_cases({"method": "DELETE", "url": "https://api.exemplo.com/clientes/1"})
    assert cases
    assert all(c["requires_confirmation"] for c in cases if c["is_mutating"])


def test_negative_cases_get_are_safe():
    cases = provider.suggest_negative_cases(
        {"method": "GET", "url": "https://api.exemplo.com/clientes/1", "auth": {"type": "bearer"}}
    )
    assert any(c["safe_to_auto_run"] for c in cases)


CUSTOMERS_CTX = {
    "json_valid": True,
    "status_code": 200,
    "body_json": {
        "customers": [
            {"id": 1, "tier": "PREMIUM", "active": True, "limit": 5000},
            {"id": 2, "tier": "PREMIUM", "active": True, "limit": 200},
            {"id": 3, "tier": "BASIC", "active": False, "limit": 50},
        ]
    },
}


def test_nl_to_rules_grounds_conditional_rule_in_real_response():
    text = "Clientes PREMIUM devem estar ativos e ter limite maior que 1000."
    result = provider.nl_to_rules(text, CUSTOMERS_CTX)
    rules = result["rules"]
    assert len(rules) == 2
    assert result["unparsed"] == []

    active_rule = next(r for r in rules if r["field"] == "active")
    assert active_rule["operator"] == "equals"
    assert active_rule["expected"] is True
    assert active_rule["array_path"] == "customers"
    assert active_rule["condition_field"] == "tier"
    assert active_rule["condition_expected"] == "PREMIUM"

    limit_rule = next(r for r in rules if r["field"] == "limit")
    assert limit_rule["operator"] == "greater_than"
    assert limit_rule["expected"] == 1000
    assert limit_rule["array_path"] == "customers"


def test_nl_to_rules_does_not_invent_condition_not_present_in_response():
    # "GOLD" nao aparece em nenhum campo desta resposta - a IA nao pode
    # inventar uma condicao sobre um valor que nunca foi observado.
    text = "Clientes GOLD devem estar ativos."
    result = provider.nl_to_rules(text, CUSTOMERS_CTX)
    assert all(r.get("array_path") is None for r in result["rules"])


def test_nl_to_rules_without_response_ctx_still_works_flat():
    # Sem response_ctx (ou resposta ainda nao testada), o comportamento
    # anterior (regra simples de campo) precisa continuar funcionando.
    result = provider.nl_to_rules("Clientes PREMIUM devem estar ativos.", None)
    assert all(r.get("array_path") is None for r in result["rules"])


def test_answer_question_field_value():
    ctx = {
        "json_valid": True,
        "body_json": {"latitude": 52.52, "elevation": 38.0, "current": {"temperature_2m": 21.4}},
    }
    answer = provider.answer_question("Qual foi o retorno do campo elevation?", ctx)
    assert "38.0" in answer


def test_answer_question_fields_inside():
    ctx = {
        "json_valid": True,
        "body_json": {"current": {"time": "2026-08-09T15:00", "temperature_2m": 21.4}},
    }
    answer = provider.answer_question("Quais campos existem dentro de current?", ctx)
    assert "time" in answer
    assert "temperature_2m" in answer


def test_answer_question_field_type():
    ctx = {"json_valid": True, "body_json": {"current": {"temperature_2m": 21.4}}}
    answer = provider.answer_question("Qual é o tipo de temperature_2m?", ctx)
    assert "number" in answer


def test_answer_question_unknown_field_lists_available():
    ctx = {"json_valid": True, "body_json": {"name": "Ana"}}
    answer = provider.answer_question("Qual o valor do campo idade_do_pet?", ctx)
    assert "não encontrei" in answer.lower()
    assert "name" in answer


def test_answer_question_without_response_says_so():
    answer = provider.answer_question("Qual o valor do campo x?", {"json_valid": False})
    assert "testar api" in answer.lower() or "não há" in answer.lower()


# --- correção do mapeamento semântico (bug real encontrado com a API do GitHub) ---
# O GitHub foi usado só para achar o bug - estes testes validam o MECANISMO
# genérico (nomes reais de campo em inglês, frase de negócio em português),
# não nada específico do GitHub.

GITHUB_REPO_CTX = {
    "json_valid": True,
    "status_code": 200,
    "body_json": {
        "id": 1296269,
        "name": "Hello-World",
        "full_name": "octocat/Hello-World",
        "private": False,
        "visibility": "public",
        "owner": {"login": "octocat", "id": 1},
        "stargazers_count": 123,
        "watchers_count": 123,
        "forks_count": 9,
        "language": "Python",
    },
}


def test_nl_maps_repository_not_private_to_real_boolean_field():
    """"repositório não seja privado" -> private == false (não pode virar
    "repositorio not_equals privado", que era o bug reportado)."""
    result = provider.nl_to_rules("Quero garantir que o repositório não seja privado.", GITHUB_REPO_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["field"] == "private"
    assert rule["operator"] == "equals"
    assert rule["expected"] is False


def test_nl_maps_star_count_phrase_to_real_field():
    """"número de estrelas maior que zero" -> stargazers_count > 0."""
    result = provider.nl_to_rules("O número de estrelas seja maior que zero.", GITHUB_REPO_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["field"] == "stargazers_count"
    assert rule["operator"] == "greater_than"
    assert rule["expected"] == 0


def test_nl_combined_github_example_from_bug_report():
    text = "Quero garantir que o repositório não seja privado e que o número de estrelas seja maior que zero."
    result = provider.nl_to_rules(text, GITHUB_REPO_CTX)
    assert result["unparsed"] == []
    fields = {r["field"] for r in result["rules"]}
    assert fields == {"private", "stargazers_count"}
    # nenhum campo inventado (ex: "repositorio", "numero", "estrelas") pode aparecer
    invented = {"repositorio", "repositório", "numero", "número", "estrelas"}
    assert not (fields & invented)


CUSTOMER_STATUS_CTX = {
    "json_valid": True,
    "body_json": {
        "customers": [
            {"id": 1, "customerType": "PREMIUM", "status": "ACTIVE", "creditLimit": 5000},
            {"id": 2, "customerType": "PREMIUM", "status": "INACTIVE", "creditLimit": 200},
            {"id": 3, "customerType": "BASIC", "status": "ACTIVE", "creditLimit": 50},
        ]
    },
}


def test_nl_conditional_premium_customers_active_maps_to_status_value():
    """"Clientes PREMIUM devem estar ativos" quando não existe campo booleano
    dedicado, mas existe status/"ACTIVE" observado -> IF customerType ==
    "PREMIUM" THEN status == "ACTIVE" (exemplo do próprio pedido)."""
    result = provider.nl_to_rules("Clientes PREMIUM devem estar ativos.", CUSTOMER_STATUS_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["array_path"] == "customers"
    assert rule["condition_field"] == "customerType"
    assert rule["condition_expected"] == "PREMIUM"
    assert rule["field"] == "status"
    assert rule["operator"] == "equals"
    assert rule["expected"] == "ACTIVE"


def test_nl_conditional_premium_credit_limit_example_from_request():
    text = "Se o cliente for PREMIUM, o limite deve ser maior que 1000."
    result = provider.nl_to_rules(text, CUSTOMER_STATUS_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["condition_field"] == "customerType"
    assert rule["condition_expected"] == "PREMIUM"
    assert rule["field"] == "creditLimit"
    assert rule["operator"] == "greater_than"
    assert rule["expected"] == 1000


def test_nl_does_not_invent_field_when_no_confident_match():
    """Requisito 4: linguagem humana nao pode gerar um campo inexistente."""
    result = provider.nl_to_rules("Quero garantir que o xyzabc123qualquercoisa seja legal.", GITHUB_REPO_CTX)
    assert result["rules"] == []
    real_field_names = set(GITHUB_REPO_CTX["body_json"].keys())
    for msg in result["unparsed"]:
        for name in real_field_names:
            assert f'"{name}"' not in msg or "corresponde a" not in msg


def test_nl_asks_for_clarification_when_unresolved():
    """Requisito 5: quando não há correspondência segura, a IA deve avisar
    que não conseguiu mapear (e não simplesmente inventar um campo)."""
    result = provider.nl_to_rules("Quero garantir que o xyzabc123qualquercoisa seja legal.", GITHUB_REPO_CTX)
    assert len(result["unparsed"]) == 1
    message = result["unparsed"][0].lower()
    assert "não consegui identificar" in message
    assert "xyzabc123qualquercoisa" in message.lower()


def test_nl_never_invents_field_across_many_unrelated_phrases():
    """Bateria adicional: nenhuma dessas frases deve produzir um campo que
    não existe de verdade na resposta do GitHub."""
    phrases = [
        "Quero garantir que o repositório seja incrível.",
        "Quero garantir que a organização seja confiável.",
        "Quero garantir que o projeto esteja completo.",
    ]
    real_field_names = set(GITHUB_REPO_CTX["body_json"].keys())
    for phrase in phrases:
        result = provider.nl_to_rules(phrase, GITHUB_REPO_CTX)
        for rule in result["rules"]:
            assert rule["field"] in real_field_names, f"campo inventado: {rule['field']!r} para {phrase!r}"


def test_pytest_still_decides_pass_fail_for_ai_proposed_rule():
    """Requisito 6: a IA só transforma linguagem em regra estruturada: quem
    decide PASS/FAIL é sempre o avaliador usado pelo pytest
    (app.engine.evaluator.evaluate_check), nunca a IA."""
    from app.engine.evaluator import evaluate_check

    result = provider.nl_to_rules("O número de estrelas seja maior que zero.", GITHUB_REPO_CTX)
    rule = result["rules"][0]
    check = {"field": rule["field"], "operator": rule["operator"], "expected": rule["expected"]}

    passing_ctx = {**GITHUB_REPO_CTX, "body_json": {**GITHUB_REPO_CTX["body_json"], "stargazers_count": 125}}
    assert evaluate_check(check, passing_ctx).passed is True

    failing_ctx = {**GITHUB_REPO_CTX, "body_json": {**GITHUB_REPO_CTX["body_json"], "stargazers_count": 0}}
    assert evaluate_check(check, failing_ctx).passed is False


# --- ajuste adicional: "mais de N", combinação de 3 regras, e ambiguidade real ---


def test_multiple_rules_in_a_single_message_teste_3():
    """TESTE 3 do pedido: uma frase com 3 regras, incluindo a construção
    'mais de N <campo>' (valor antes do campo), deve gerar as 3 regras
    corretas usando os campos reais do GitHub."""
    text = "Quero garantir que o repositório não seja privado, tenha mais de 100 estrelas e mais de 10 forks."
    result = provider.nl_to_rules(text, GITHUB_REPO_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 3

    by_field = {r["field"]: r for r in result["rules"]}
    assert by_field["private"]["operator"] == "equals"
    assert by_field["private"]["expected"] is False
    assert by_field["stargazers_count"]["operator"] == "greater_than"
    assert by_field["stargazers_count"]["expected"] == 100
    assert by_field["forks_count"]["operator"] == "greater_than"
    assert by_field["forks_count"]["expected"] == 10


def test_repository_public_prefers_real_boolean_field_over_string_field():
    """Quando existe um campo booleano de verdade para o conceito (aqui,
    'private', via o antônimo de 'público'), ele tem prioridade sobre um
    campo string que só bate pelo nome ('visibility') - resultado esperado
    explicitamente pelo pedido: private == false, não visibility=="public"
    nem (o bug original) visibility==True/False."""
    ctx = {"json_valid": True, "body_json": {"private": False, "visibility": "public"}}
    result = provider.nl_to_rules("O repositório deve ser público.", ctx)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["field"] == "private"
    assert rule["operator"] == "equals"
    assert rule["expected"] is False


def test_visibility_string_field_still_used_when_no_boolean_field_exists():
    """Continua funcionando quando SÓ existe o campo string (sem 'private')
    - aqui não há campo booleano real para preferir, então o valor
    observado ("public") é usado corretamente, nunca um True/False."""
    ctx = {"json_valid": True, "body_json": {"visibility": "public"}}
    result = provider.nl_to_rules("O repositório deve ser público.", ctx)
    assert result["unparsed"] == []
    rule = result["rules"][0]
    assert rule["field"] == "visibility"
    assert rule["operator"] == "equals"
    assert rule["expected"] == "public"


def test_ambiguous_field_asks_for_clarification_teste_5():
    """TESTE 5: quando mais de um campo real é igualmente plausível (aqui,
    'estado' bate igualmente com 'status' e 'state', sem nenhum valor real
    para desempatar), a IA não deve escolher silenciosamente nem inventar -
    deve sinalizar a ambiguidade e listar os candidatos encontrados."""
    ctx = {"json_valid": True, "body_json": {"status": "PENDING", "state": "PENDING"}}
    result = provider.nl_to_rules("Quero garantir que o estado seja PENDENTE.", ctx)
    assert result["rules"] == []
    assert len(result["unparsed"]) == 1
    message = result["unparsed"][0]
    assert "não consegui identificar" in message.lower()
    assert "status" in message
    assert "state" in message


# --- ajuste final: "pelo menos", campo semanticamente mais preciso, ---
# --- não inventar campo, sintaxe técnica explícita                  ---


def test_at_least_n_forks_maps_to_greater_than_or_equal():
    """Requisito 1 / TESTE 3: "pelo menos N" -> greater_than_or_equal,
    reaproveitando o operador já existente (nenhum operador novo)."""
    result = provider.nl_to_rules("Quero garantir que o número de forks seja pelo menos 10.", GITHUB_REPO_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["field"] == "forks_count"
    assert rule["operator"] == "greater_than_or_equal"
    assert rule["expected"] == 10


def test_at_least_equivalent_phrasings_all_map_to_greater_than_or_equal():
    phrasings = [
        "Quero garantir que o repositório tenha pelo menos 10 forks.",
        "Quero garantir que o repositório tenha no mínimo 10 forks.",
        "Quero garantir que o repositório tenha 10 ou mais forks.",
        "Quero garantir que o número de forks seja maior ou igual a 10.",
    ]
    for text in phrasings:
        result = provider.nl_to_rules(text, GITHUB_REPO_CTX)
        assert result["unparsed"] == [], f"falhou para: {text!r} -> {result['unparsed']}"
        forks_rules = [r for r in result["rules"] if r["field"] == "forks_count"]
        assert len(forks_rules) == 1, f"falhou para: {text!r}"
        assert forks_rules[0]["operator"] == "greater_than_or_equal"
        assert forks_rules[0]["expected"] == 10


def test_three_rules_combined_teste_3_from_request():
    text = (
        "Quero garantir que o repositório não seja privado, "
        "tenha mais de 100 estrelas e tenha pelo menos 10 forks."
    )
    result = provider.nl_to_rules(text, GITHUB_REPO_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 3
    by_field = {r["field"]: r for r in result["rules"]}
    assert by_field["private"]["expected"] is False
    assert by_field["stargazers_count"]["operator"] == "greater_than"
    assert by_field["stargazers_count"]["expected"] == 100
    assert by_field["forks_count"]["operator"] == "greater_than_or_equal"
    assert by_field["forks_count"]["expected"] == 10


def test_repository_name_maps_to_precise_field_not_full_name():
    """Requisito 2 / TESTE 4 e 6: "nome do repositório" -> name, não
    full_name, mesmo com os dois campos presentes na resposta real."""
    result = provider.nl_to_rules("Quero garantir que o nome do repositório seja Hello-World.", GITHUB_REPO_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["field"] == "name"
    assert rule["operator"] == "equals"
    assert rule["expected"] == "Hello-World"


def test_full_name_phrase_maps_to_full_name_field():
    """Contraste do teste acima: "nome COMPLETO" deve resolver para
    full_name, provando que a escolha é semântica e não um "sempre usar o
    campo mais curto"."""
    result = provider.nl_to_rules(
        "Quero garantir que o nome completo do repositório seja octocat/Hello-World.", GITHUB_REPO_CTX
    )
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    assert result["rules"][0]["field"] == "full_name"


GITHUB_REPO_WITH_URLS_CTX = {
    "json_valid": True,
    "body_json": {
        **GITHUB_REPO_CTX["body_json"],
        "releases_url": "https://api.github.com/repos/octocat/Hello-World/releases{/id}",
    },
}


def test_does_not_invent_field_for_unrelated_business_rule_teste_5():
    """Requisito 3 / TESTE 5: regra de negócio de "cliente"/"Premium"/
    "ativo" contra uma resposta do GitHub (sem nenhum campo de cliente) não
    pode inventar um campo qualquer (bug real: "releases_url equals ativo",
    causado por um candidato curto ("ele") batendo por coincidência de
    substring dentro de "releases_url")."""
    text = "Se o cliente for Premium, quero garantir que ele esteja ativo."
    result = provider.nl_to_rules(text, GITHUB_REPO_WITH_URLS_CTX)
    # nenhuma regra foi criada apontando para um campo (releases_url ou
    # qualquer outro) que nao tem relacao real com "cliente"/"ativo" - a
    # mensagem de esclarecimento pode LISTAR releases_url como um dos
    # "campos disponiveis" (isso e informativo, nao uma escolha), mas isso
    # e bem diferente de uma Rule ter sido criada com esse campo.
    assert result["rules"] == []


# --- regra condicional sobre resposta PLANA (sem lista) ---
# "Se o repositório for público, quero garantir que tenha mais de 100 estrelas."


def test_flat_conditional_rule_from_request_example():
    text = "Se o repositório for público, quero garantir que ele tenha mais de 100 estrelas."
    result = provider.nl_to_rules(text, GITHUB_REPO_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["array_path"] == ""
    assert rule["condition_field"] == "private"
    assert rule["condition_operator"] == "equals"
    assert rule["condition_expected"] is False
    assert rule["field"] == "stargazers_count"
    assert rule["operator"] == "greater_than"
    assert rule["expected"] == 100


GITHUB_REPO_PRIVATE_ONLY_CTX = {
    "json_valid": True,
    "body_json": {"name": "Hello-World", "private": False, "stargazers_count": 3755, "forks_count": 120},
}


def test_flat_conditional_resolves_via_antonym_when_no_visibility_field():
    """Quando a resposta só tem o campo booleano 'private' (sem 'visibility'
    nem 'public'), "for público" precisa resolver via o antônimo real
    (private == false), sem inventar um campo 'public' que não existe."""
    text = "Se o repositório for público, quero garantir que ele tenha mais de 100 estrelas."
    result = provider.nl_to_rules(text, GITHUB_REPO_PRIVATE_ONLY_CTX)
    assert result["unparsed"] == []
    rule = result["rules"][0]
    assert rule["condition_field"] == "private"
    assert rule["condition_expected"] is False
    assert rule["field"] == "stargazers_count"


def test_flat_conditional_unresolved_condition_does_not_invent_field():
    """Se a condição não puder ser mapeada com segurança, nenhuma regra deve
    ser criada (nem a condição, nem a consequência) - não pode "perder" a
    condição silenciosamente e virar uma regra simples incorreta."""
    text = "Se o cliente for Premium, quero garantir que ele tenha mais de 100 estrelas."
    result = provider.nl_to_rules(text, GITHUB_REPO_CTX)
    assert result["rules"] == []
    assert len(result["unparsed"]) == 1
    assert "condição" in result["unparsed"][0].lower()


def test_preserves_existing_tests_conditional_and_flat_still_pass():
    """Requisito 10: casos já cobertos por rodadas anteriores continuam
    funcionando após esta correção (checagem rápida e direta aqui, além da
    suíte completa)."""
    flat = provider.nl_to_rules("Quero garantir que o repositório não seja privado.", GITHUB_REPO_CTX)
    assert flat["rules"][0]["field"] == "private"
    assert flat["rules"][0]["expected"] is False

    result = provider.nl_to_rules("Clientes PREMIUM devem estar ativos.", CUSTOMER_STATUS_CTX)
    assert result["rules"][0]["array_path"] == "customers"
    assert result["rules"][0]["field"] == "status"
    assert result["rules"][0]["expected"] == "ACTIVE"


# --- rodada final: condição negativa (privado), regra estruturada + SKIP, genericidade ---


def test_flat_conditional_negative_case_private_true():
    """Frase-espelho do teste negativo pedido: "for privado" precisa
    resolver para private == true (não string "privado")."""
    text = "Se o repositório for privado, quero garantir que ele tenha mais de 1000000 estrelas."
    result = provider.nl_to_rules(text, GITHUB_REPO_CTX)
    assert result["unparsed"] == []
    rule = result["rules"][0]
    assert rule["condition_field"] == "private"
    assert rule["condition_operator"] == "equals"
    assert rule["condition_expected"] is True
    assert rule["field"] == "stargazers_count"
    assert rule["operator"] == "greater_than"
    assert rule["expected"] == 1000000


def test_ai_conditional_rule_is_same_structure_pytest_evaluates():
    """P/Q: a regra que a IA propõe para uma condicional já é a MESMA
    estrutura (field/operator/expected + condition_field/condition_operator/
    condition_expected) que o motor de avaliação usa - sem motor paralelo.
    Aqui alimentamos o dict da IA direto em evaluate_check (o mesmo caminho
    que o pytest real usa) para provar isso ponta a ponta."""
    from app.engine.evaluator import evaluate_check

    text = "Se o repositório for público, quero garantir que ele tenha mais de 100 estrelas."
    ai_rule = provider.nl_to_rules(text, GITHUB_REPO_CTX)["rules"][0]

    check = {
        "field": ai_rule["field"],
        "operator": ai_rule["operator"],
        "expected": str(ai_rule["expected"]),
        "array_path": ai_rule["array_path"],
        "condition_field": ai_rule["condition_field"],
        "condition_operator": ai_rule["condition_operator"],
        "condition_expected": str(ai_rule["condition_expected"]),
    }

    # condicao verdadeira (private=False no response real) -> regra avaliada normalmente
    r_true = evaluate_check(check, GITHUB_REPO_CTX)
    assert not r_true.skipped
    assert r_true.passed  # 3755 > 100

    # condicao falsa (simulando um repo privado) -> SKIPPED, nunca PASS/FAIL
    ctx_private = {**GITHUB_REPO_CTX, "body_json": {**GITHUB_REPO_CTX["body_json"], "private": True}}
    r_false = evaluate_check(check, ctx_private)
    assert r_false.skipped


def test_generic_api_customer_credit_limit_not_github_specific():
    """Requisito 12: mesmo mecanismo, API totalmente diferente do GitHub -
    prova que nada aqui é hardcoded para stargazers_count/private/forks."""
    ctx = {"json_valid": True, "body_json": {"customer": {"active": True, "credit_limit": 5000}}}
    result = provider.nl_to_rules(
        "Quero garantir que o cliente esteja ativo e tenha limite maior que 1000.", ctx
    )
    assert result["unparsed"] == []
    fields = {r["field"] for r in result["rules"]}
    assert fields == {"customer.active", "customer.credit_limit"}
    active_rule = next(r for r in result["rules"] if r["field"] == "customer.active")
    assert active_rule["expected"] is True
    limit_rule = next(r for r in result["rules"] if r["field"] == "customer.credit_limit")
    assert limit_rule["operator"] == "greater_than"
    assert limit_rule["expected"] == 1000


# ============================================================
# Ajuste "Assistente de IA" - testes obrigatórios numerados exatamente como
# pedido. NÃO tocam em nenhuma estrutura do fluxo manual (RuleBuilder,
# ManualBusinessRules, execuções) - só chamam HeuristicAIProvider.nl_to_rules
# diretamente, o mesmo provider já coberto pelos testes acima.
# ============================================================

AI_TEST_GITHUB_CTX = {
    "json_valid": True,
    "status_code": 200,
    "body_json": {
        "name": "Hello-World",
        "private": False,
        "stargazers_count": 3755,
        "forks_count": 120,
        "owner": {"login": "octocat", "id": 1},
    },
}


def test_ia_teste_1_estrelas_maior_que_100():
    text = "Quero garantir que o número de estrelas seja maior que 100."
    result = provider.nl_to_rules(text, AI_TEST_GITHUB_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["field"] == "stargazers_count"
    assert rule["operator"] == "greater_than"
    assert rule["expected"] == 100


def test_ia_teste_2_nao_seja_privado():
    result = provider.nl_to_rules("Quero garantir que o repositório não seja privado.", AI_TEST_GITHUB_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["field"] == "private"
    assert rule["operator"] == "equals"
    assert rule["expected"] is False


def test_ia_teste_3_nome_do_repositorio():
    result = provider.nl_to_rules("Quero garantir que o nome do repositório seja Hello-World.", AI_TEST_GITHUB_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["field"] == "name"
    assert rule["operator"] == "equals"
    assert rule["expected"] == "Hello-World"


def test_ia_teste_4_condicional_publico_verdadeiro():
    text = "Se o repositório for público, quero garantir que tenha mais de 100 estrelas."
    result = provider.nl_to_rules(text, AI_TEST_GITHUB_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    # estrutura condicional REAL (condition + then), nao uma string -
    # reaproveita os mesmos campos array_path/condition_* que o motor de
    # avaliação (evaluator.py) e o fluxo manual já usam.
    assert rule["condition_field"] == "private"
    assert rule["condition_operator"] == "equals"
    assert rule["condition_expected"] is False
    assert rule["field"] == "stargazers_count"
    assert rule["operator"] == "greater_than"
    assert rule["expected"] == 100


def test_ia_teste_5_condicional_privado():
    text = "Se o repositório for privado, quero garantir que tenha mais de 1000000 estrelas."
    result = provider.nl_to_rules(text, AI_TEST_GITHUB_CTX)
    assert result["unparsed"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["condition_field"] == "private"
    assert rule["condition_operator"] == "equals"
    assert rule["condition_expected"] is True
    assert rule["field"] == "stargazers_count"
    assert rule["operator"] == "greater_than"
    assert rule["expected"] == 1000000


def test_ia_teste_6_nunca_inventa_campo_a_partir_de_texto_humano():
    invented_field_names = {
        "repositório",
        "repositorio",
        "nome do repositório",
        "nome do repositorio",
        "número de estrelas",
        "numero de estrelas",
        "se o repositório",
        "se o repositorio",
        "star",
        "stars",
    }

    scenarios = [
        "Quero garantir que o repositório seja incrível.",
        "Quero garantir que o número de estrelas seja maior que 100.",
        "Quero garantir que o nome do repositório seja Hello-World.",
        "Se o repositório for público, quero garantir que tenha mais de 100 estrelas.",
        "Se o repositório for privado, quero garantir que tenha mais de 1000000 estrelas.",
    ]
    for text in scenarios:
        result = provider.nl_to_rules(text, AI_TEST_GITHUB_CTX)
        for rule in result["rules"]:
            field_norm = (rule["field"] or "").strip().lower()
            assert field_norm not in invented_field_names, f"campo inventado {rule['field']!r} para {text!r}"
            condition_field = rule.get("condition_field")
            if condition_field:
                assert condition_field.strip().lower() not in invented_field_names


# ============================================================
# Assistente de IA - escopo final: SOMENTE 2 funções isoladas do fluxo
# manual (ManualBusinessRules, RuleBuilder, execuções, pytest). Os testes
# abaixo mantêm a numeração histórica ("Teste N") de quando o assistente
# tinha 5 funções; "Analisar requisito complexo", "Encontrar campo" e
# "Explicar campo" foram removidas da interface e do fluxo da IA (endpoints
# /ai/suggest-field, /ai/explain-field e os métodos exclusivos
# suggest_field/explain_field do provider deixaram de existir), então os
# testes que cobriam exclusivamente essas 3 funções também foram removidos
# daqui. Nenhum teste abaixo toca em ManualBusinessRules.tsx nem em
# nenhuma estrutura do fluxo manual - só exercitam parse_multiple_lines
# (Função 1, determinístico) e HeuristicAIProvider.suggest_scenarios
# (Função 2).
# ============================================================


def test_teste_1_funcao1_regra_unica_stargazers_maior_que_100():
    result = parse_multiple_lines("stargazers_count > 100", ["stargazers_count", "private", "name", "forks_count"])
    assert result["errors"] == []
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["field"] == "stargazers_count"
    assert rule["operator"] == "greater_than"
    assert rule["expected"] == 100


def test_teste_2_funcao1_multiplas_regras_independentes():
    known_fields = ["stargazers_count", "private", "name", "forks_count"]
    text = "stargazers_count > 100\nprivate == false\nname == Hello-World\nforks_count >= 10"
    result = parse_multiple_lines(text, known_fields)
    assert result["errors"] == []
    assert len(result["rules"]) == 4
    by_field = {r["field"]: r for r in result["rules"]}
    assert by_field["stargazers_count"]["operator"] == "greater_than"
    assert by_field["stargazers_count"]["expected"] == 100
    assert by_field["private"]["operator"] == "equals"
    assert by_field["private"]["expected"] is False
    assert by_field["name"]["operator"] == "equals"
    assert by_field["name"]["expected"] == "Hello-World"
    assert by_field["forks_count"]["operator"] == "greater_than_or_equal"
    assert by_field["forks_count"]["expected"] == 10


def test_teste_3_funcao1_tipo_booleano_respeitado():
    result = parse_multiple_lines("private == false", ["private"])
    rule = result["rules"][0]
    assert rule["expected"] is False
    assert isinstance(rule["expected"], bool)


def test_teste_4_funcao1_tipo_numerico_respeitado():
    result = parse_multiple_lines("stargazers_count > 100", ["stargazers_count"])
    rule = result["rules"][0]
    assert rule["expected"] == 100
    assert isinstance(rule["expected"], int)
    assert not isinstance(rule["expected"], str)


def test_teste_5_funcao1_campo_inexistente_e_rejeitado_sem_adivinhar():
    known_fields = ["stargazers_count", "private", "name", "forks_count"]
    result = parse_multiple_lines("stars > 100", known_fields)
    assert result["rules"] == []
    assert len(result["errors"]) == 1
    assert result["errors"][0] == "Campo \"stars\" não encontrado na resposta da API. Use o nome real do campo."
    # nunca deve mapear silenciosamente "stars" para "stargazers_count"
    assert "stargazers_count" not in result["errors"][0]


def test_teste_7_funcao2_sugere_cenarios_para_credit_limit_maior_que_5000():
    check = {"field": "credit_limit", "operator": "greater_than", "expected": 5000}
    scenarios = provider.suggest_scenarios(check)
    assert len(scenarios) == 3
    by_outcome = [(s["value"], s["expected_outcome"]) for s in scenarios]
    assert (6000, "PASS") in by_outcome
    assert (5000, "FAIL") in by_outcome
    assert (4999, "FAIL") in by_outcome
