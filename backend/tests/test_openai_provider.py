"""OpenAIProvider (melhoria "IA generativa real com OpenAI"). Cobre, com o
SDK da OpenAI MOCKADO (nunca gasta créditos reais nos testes automatizados
— o teste real de integração é manual/documentado, não faz parte do CI):

  1. is_available() reflete só a CONFIGURAÇÃO (chave presente), sem chamada
     de rede — chamar a OpenAI de verdade só pra checar disponibilidade
     custaria dinheiro a cada GET /api/ai/status;
  2. sucesso: chat()/suggest_test_data()/nl_to_rules()/... usam a resposta
     real do "modelo";
  3. qualquer falha (rede, autenticação, JSON inválido) cai para o
     HeuristicAIProvider automaticamente — a plataforma nunca quebra por
     causa da OpenAI estar fora do ar, e a falha fica visível no log
     (capturada aqui via capsys) em vez de mascarada como resposta normal;
  4. os métodos deterministicos (suggest_negative_cases/suggest_scenarios)
     nunca chamam a OpenAI, mesmo com a chave configurada.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.core import config


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def _fake_openai_class(content_or_exc):
    """Fábrica de uma classe `OpenAI` falsa compatível com o formato usado
    por OpenAIProvider: `client.chat.completions.create(...).choices[0].
    message.content`. Se `content_or_exc` for uma Exception, a chamada
    levanta essa exceção (simula falha de rede/autenticação/etc)."""

    def _create(**_kwargs):
        if isinstance(content_or_exc, Exception):
            raise content_or_exc
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content_or_exc))])

    class _FakeOpenAI:
        def __init__(self, api_key=None, timeout=None):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))

    return _FakeOpenAI


def _make_provider(monkeypatch, api_key="test-key", content_or_exc="ok"):
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    config.get_settings.cache_clear()
    monkeypatch.setattr("openai.OpenAI", _fake_openai_class(content_or_exc))
    from app.ai.openai_provider import OpenAIProvider

    return OpenAIProvider()


# --- configuração / disponibilidade -------------------------------------------


def test_is_available_false_sem_chave(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config.get_settings.cache_clear()
    from app.ai.openai_provider import OpenAIProvider

    assert OpenAIProvider().is_available() is False


def test_is_available_true_com_chave_sem_chamada_de_rede(monkeypatch):
    def _boom(**_kwargs):
        raise AssertionError("is_available não deveria fazer nenhuma chamada de rede")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config.get_settings.cache_clear()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_boom)))
    monkeypatch.setattr("openai.OpenAI", lambda **kw: fake_client)
    from app.ai.openai_provider import OpenAIProvider

    provider = OpenAIProvider()
    assert provider.is_available() is True


def test_describe_expoe_nome_e_disponibilidade(monkeypatch):
    provider = _make_provider(monkeypatch)
    assert provider.describe() == {"name": "openai", "available": True}


def test_modelo_e_configuravel_por_env_var(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("API_TESTFLOW_OPENAI_MODEL", "gpt-4o")
    config.get_settings.cache_clear()
    from app.ai.openai_provider import OpenAIProvider

    assert OpenAIProvider()._model == "gpt-4o"


# --- chat() -------------------------------------------------------------------


def test_chat_usa_resposta_real_do_modelo(monkeypatch):
    provider = _make_provider(monkeypatch, content_or_exc="Esta API retorna produtos de um catálogo.")
    result = provider.chat("Explique essa API", {"method": "GET", "url": "https://x.com"})
    assert result == "Esta API retorna produtos de um catálogo."


def test_chat_cai_para_heuristica_sem_chave_configurada(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config.get_settings.cache_clear()
    from app.ai.openai_provider import OpenAIProvider

    result = OpenAIProvider().chat("Explique essa API", {"method": "GET", "url": "https://x.com"})
    assert "GET" in result  # veio do HeuristicAIProvider.chat


def test_chat_cai_para_heuristica_e_loga_em_falha_de_rede(monkeypatch, capsys):
    provider = _make_provider(monkeypatch, content_or_exc=ConnectionError("network down"))
    result = provider.chat("Explique esse erro 403", {})
    assert "permiss" in result.lower()  # heurística reconhece 403
    captured = capsys.readouterr()
    assert "openai_provider" in captured.out
    assert "ConnectionError" in captured.out


# --- suggest_test_data() -------------------------------------------------------


def test_suggest_test_data_usa_json_do_modelo(monkeypatch):
    rows = [{"cpf": "1", "idade": 30}, {"cpf": "2", "idade": 40}]
    provider = _make_provider(monkeypatch, content_or_exc=json.dumps({"rows": rows}))
    result = provider.suggest_test_data(["cpf", "idade"], None, 2)
    assert result["rows"] == rows


def test_suggest_test_data_cai_para_heuristica_com_json_invalido(monkeypatch):
    provider = _make_provider(monkeypatch, content_or_exc="isto não é json")
    result = provider.suggest_test_data(["cpf"], None, 3)
    assert len(result["rows"]) == 3


def test_suggest_test_data_sem_variaveis_nao_chama_o_modelo(monkeypatch):
    def _boom(**_kwargs):
        raise AssertionError("não deveria chamar a OpenAI sem variáveis")

    provider = _make_provider(monkeypatch, content_or_exc="ignorado")
    provider._client_or_none = lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_boom))
    )
    result = provider.suggest_test_data([], None, 5)
    assert result["columns"] == []


# --- nl_to_rules() --------------------------------------------------------------


def test_nl_to_rules_usa_json_do_modelo(monkeypatch):
    payload = {
        "rules": [{"field": "status", "operator": "equals", "expected": "ACTIVE", "description": "status ok"}],
        "unparsed": [],
    }
    provider = _make_provider(monkeypatch, content_or_exc=json.dumps(payload))
    result = provider.nl_to_rules("status deve ser ACTIVE", None)
    assert result["rules"][0]["field"] == "status"
    assert result["rules"][0]["source"] == "ai_suggested"
    assert result["rules"][0]["id"]  # id gerado, nunca vazio


def test_nl_to_rules_cai_para_heuristica_sem_campo_rules(monkeypatch):
    provider = _make_provider(monkeypatch, content_or_exc=json.dumps({"algo_errado": True}))
    result = provider.nl_to_rules("o status seja ACTIVE", None)
    assert "rules" in result  # veio do fallback, que sempre devolve essa chave


# --- métodos deterministicos nunca chamam a OpenAI -----------------------------


def test_suggest_negative_cases_nunca_chama_a_openai(monkeypatch):
    def _boom(**_kwargs):
        raise AssertionError("suggest_negative_cases não deveria chamar a OpenAI")

    provider = _make_provider(monkeypatch, content_or_exc="ignorado")
    provider._client_or_none = lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_boom))
    )
    provider.suggest_negative_cases({"method": "GET", "url": "https://x.com/1"})


def test_suggest_scenarios_nunca_chama_a_openai(monkeypatch):
    def _boom(**_kwargs):
        raise AssertionError("suggest_scenarios não deveria chamar a OpenAI")

    provider = _make_provider(monkeypatch, content_or_exc="ignorado")
    provider._client_or_none = lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_boom))
    )
    provider.suggest_scenarios({"field": "age", "operator": "greater_than", "expected": 18})


# --- factory ---------------------------------------------------------------------


def test_factory_seleciona_openai_provider(monkeypatch):
    monkeypatch.setenv("API_TESTFLOW_AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config.get_settings.cache_clear()
    from app.ai.factory import get_ai_provider

    get_ai_provider.cache_clear()
    provider = get_ai_provider()
    assert provider.name == "openai"
    get_ai_provider.cache_clear()
