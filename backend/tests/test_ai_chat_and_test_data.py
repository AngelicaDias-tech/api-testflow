"""Assistente de IA (chat) e geração de massa via IA (melhorias "LLM real"
e "Assistente de IA"). Cobre o provider heurístico (determinístico, sem
rede) para chat() e suggest_test_data() - garantia central da seção 12: a
ausência de IA "de verdade" nunca impede o uso da plataforma. O provider
real (OpenAIProvider, com HTTP mockado) tem cobertura equivalente em
tests/test_openai_provider.py.
"""

from __future__ import annotations

import httpx

from app.ai.heuristic_provider import HeuristicAIProvider

provider = HeuristicAIProvider()


# --- HeuristicAIProvider.chat -------------------------------------------------


def test_chat_explica_api_com_contexto_disponivel():
    answer = provider.chat(
        "Explique essa API",
        {"method": "GET", "url": "https://api.exemplo.com/clientes/1", "status_code": 200, "body_json": {"id": 1}},
    )
    assert "GET" in answer
    assert "api.exemplo.com" in answer


def test_chat_explica_status_http_conhecido():
    answer = provider.chat("Explique esse erro 401", {})
    assert "token" in answer.lower()


def test_chat_sugere_campos_importantes():
    answer = provider.chat(
        "Quais campos são importantes de validar?",
        {"body_json": {"id": 1, "status": "ACTIVE", "items": [1, 2, 3]}, "status_code": 200},
    )
    assert "id" in answer


def test_chat_responde_pergunta_pontual_via_answer_question():
    answer = provider.chat("qual o valor do campo status", {"body_json": {"status": "ACTIVE"}})
    assert "ACTIVE" in answer


def test_chat_e_honesto_quando_nao_reconhece_a_pergunta_sem_contexto():
    answer = provider.chat("me conte uma piada", {})
    assert "heurístic" in answer.lower() or "openai" in answer.lower()


def test_chat_nunca_afirma_decidir_pass_fail():
    for message, ctx in [
        ("Explique essa API", {"method": "GET", "url": "https://x.com"}),
        ("Explique esse erro 500", {}),
        ("qual o valor do campo id", {"body_json": {"id": 1}}),
    ]:
        answer = provider.chat(message, ctx)
        assert "PASS" not in answer and "FAIL" not in answer


# --- HeuristicAIProvider.suggest_test_data -------------------------------------


def test_suggest_test_data_gera_numero_de_casos_pedido():
    result = provider.suggest_test_data(["cpf", "idade", "valor"], None, 5)
    assert result["columns"] == ["cpf", "idade", "valor"]
    assert len(result["rows"]) == 5
    assert all(set(row.keys()) == {"cpf", "idade", "valor"} for row in result["rows"])


def test_suggest_test_data_infere_tipos_plausiveis_por_nome():
    result = provider.suggest_test_data(["idade", "ativo", "email"], None, 3)
    assert all(isinstance(row["idade"], int) for row in result["rows"])
    assert all(isinstance(row["ativo"], bool) for row in result["rows"])
    assert all("@" in row["email"] for row in result["rows"])


def test_suggest_test_data_limita_quantidade_maxima_defensivamente():
    result = provider.suggest_test_data(["cpf"], None, 10_000)
    assert len(result["rows"]) <= 200


def test_suggest_test_data_nunca_executa_chamada(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("suggest_test_data não deveria fazer nenhuma chamada de rede")

    monkeypatch.setattr(httpx, "get", _boom)
    monkeypatch.setattr(httpx, "post", _boom)
    provider.suggest_test_data(["cpf", "idade"], None, 3)
