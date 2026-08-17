"""
Escolhe o provider de IA pela configuracao (secao 12/28). Arquitetura
final: HeuristicAIProvider (padrao, sem dependencias externas) ou
OpenAIProvider (LLM real em nuvem, opt-in via API_TESTFLOW_AI_PROVIDER=
openai). Qualquer novo provider futuro so precisa implementar
app.ai.base.AIProvider e ser registrado aqui - o resto da aplicacao
(app/api/ai.py, o Assistente de IA no frontend) nunca muda.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai.base import AIProvider
from app.ai.heuristic_provider import HeuristicAIProvider
from app.core.config import get_settings


@lru_cache
def get_ai_provider() -> AIProvider:
    settings = get_settings()
    if settings.ai_provider == "openai":
        from app.ai.openai_provider import OpenAIProvider

        return OpenAIProvider()
    return HeuristicAIProvider()
