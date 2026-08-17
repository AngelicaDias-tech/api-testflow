"""
Configuracao central da aplicacao.

Por que existe: manter toda a configuracao (banco, provedor de IA, chave de
criptografia) em um unico lugar, lida a partir de variaveis de ambiente,
evita "magic values" espalhados pelo codigo e permite trocar comportamento
(ex: qual provedor de IA usar) sem alterar codigo-fonte.
"""

from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    """As variaveis de ambiente sao lidas dentro de `__init__` (nao como
    valor padrao de atributo de classe) DE PROPOSITO: um valor padrao de
    classe (`attr: str = os.getenv(...)`) so e avaliado UMA VEZ, quando
    este modulo e importado pela primeira vez no processo - qualquer
    mudanca de variavel de ambiente depois disso (ex: `monkeypatch.setenv`
    em um teste, ou `os.environ[...] = ...` em runtime) nunca seria
    refletida em uma nova `Settings()`, mesmo limpando o cache de
    `get_settings()`. Lendo em `__init__`, cada nova instancia reflete o
    ambiente ATUAL - e o que permite os testes (ver tests/test_openai_
    provider.py, tests/test_export_import.py) trocarem provider/banco/
    chave por teste com seguranca."""

    def __init__(self) -> None:
        # SQLite e o storage inicial (secao 28) por ser zero-config e gratuito.
        self.database_url = os.getenv("API_TESTFLOW_DATABASE_URL", "sqlite:///./api_testflow.db")

        # Provedor de IA: "heuristic" (padrao, sem dependencias externas e
        # sem custo - o sistema PRECISA funcionar sem IA, secao 12) ou
        # "openai" (LLM real em nuvem, opt-in explicito). Arquitetura
        # preparada para novos providers no futuro sem reescrever nada
        # (ver app/ai/factory.py) - so nao ha nenhum outro implementado hoje.
        self.ai_provider = os.getenv("API_TESTFLOW_AI_PROVIDER", "heuristic")

        # OpenAI: a chave usa o nome de variavel PADRAO da propria OpenAI/SDK
        # (OPENAI_API_KEY, sem prefixo) - de proposito, para funcionar direto
        # se o ambiente ja tiver essa variavel definida para outra
        # ferramenta. NUNCA tem um valor default: sem ela,
        # OpenAIProvider.is_available() e False e o factory so a usa se
        # API_TESTFLOW_AI_PROVIDER=openai for escolhido explicitamente
        # (nunca acidental, nunca cobra nada por padrao).
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("API_TESTFLOW_OPENAI_MODEL", "gpt-4o-mini")
        self.openai_timeout_seconds = float(os.getenv("API_TESTFLOW_OPENAI_TIMEOUT", "60"))

        # Chave simetrica usada para nao persistir segredos (tokens/senhas)
        # em texto puro no banco (secao 29). Em producao, defina via
        # variavel de ambiente; em dev, uma chave fixa e gerada e
        # reaproveitada localmente.
        self.secret_key = os.getenv("API_TESTFLOW_SECRET_KEY", "")

        # Tempo maximo (segundos) que uma requisicao de teste pode levar.
        self.http_timeout_seconds = float(os.getenv("API_TESTFLOW_HTTP_TIMEOUT", "15"))

        self.cors_origins = os.getenv(
            "API_TESTFLOW_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()
