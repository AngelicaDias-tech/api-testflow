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
    # SQLite e o storage inicial (secao 28) por ser zero-config e gratuito.
    database_url: str = os.getenv("API_TESTFLOW_DATABASE_URL", "sqlite:///./api_testflow.db")

    # Provedor de IA: "heuristic" (padrao, sem dependencias externas) ou "ollama".
    # O sistema PRECISA funcionar sem IA (secao 12), entao o padrao nunca exige
    # servicos externos ou pagos.
    ai_provider: str = os.getenv("API_TESTFLOW_AI_PROVIDER", "heuristic")
    ollama_base_url: str = os.getenv("API_TESTFLOW_OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("API_TESTFLOW_OLLAMA_MODEL", "llama3.2")

    # Chave simetrica usada para nao persistir segredos (tokens/senhas) em
    # texto puro no banco (secao 29). Em producao, defina via variavel de
    # ambiente; em dev, uma chave fixa e gerada e reaproveitada localmente.
    secret_key: str = os.getenv("API_TESTFLOW_SECRET_KEY", "")

    # Tempo maximo (segundos) que uma requisicao de teste pode levar.
    http_timeout_seconds: float = float(os.getenv("API_TESTFLOW_HTTP_TIMEOUT", "15"))

    cors_origins: list[str] = os.getenv(
        "API_TESTFLOW_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()
