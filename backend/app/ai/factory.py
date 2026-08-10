from __future__ import annotations

from functools import lru_cache

from app.ai.base import AIProvider
from app.ai.heuristic_provider import HeuristicAIProvider
from app.core.config import get_settings


@lru_cache
def get_ai_provider() -> AIProvider:
    settings = get_settings()
    if settings.ai_provider == "ollama":
        from app.ai.ollama_provider import OllamaProvider

        return OllamaProvider()
    return HeuristicAIProvider()
