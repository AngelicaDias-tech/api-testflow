"""
Provedor de IA opcional via Ollama (secao 12/28) - modelo local, gratuito,
sem enviar dados para a nuvem. So e usado se o usuario configurar
API_TESTFLOW_AI_PROVIDER=ollama E o Ollama estiver rodando localmente.

Se o Ollama nao responder, cada metodo cai automaticamente para o
HeuristicAIProvider (composicao, nao heranca) - a ausencia da IA "de
verdade" nunca impede o uso da plataforma (secao 12/14).

Segredos nunca sao enviados ao modelo (secao 29): os prompts usam apenas
a definicao da requisicao com headers sensiveis mascarados.
"""

from __future__ import annotations

import json

import httpx

from app.ai.base import AIProvider
from app.ai.heuristic_provider import HeuristicAIProvider
from app.core.config import get_settings


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model
        self._fallback = HeuristicAIProvider()

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self._base_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def _generate_json(self, prompt: str) -> dict | None:
        try:
            resp = httpx.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=20.0,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "")
            return json.loads(text)
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            return None

    def suggest_from_response(self, response_ctx: dict, discovered_checks: list[dict]) -> dict:
        if not self.is_available():
            return self._fallback.suggest_from_response(response_ctx, discovered_checks)
        prompt = (
            "Você é um assistente de QA. Dado o corpo JSON de uma resposta de API abaixo, "
            "sugira validações adicionais úteis (não repita checagens óbvias de tipo/existência). "
            "Responda em JSON: {\"summary\": str, \"suggestions\": []}.\n\n"
            f"status_code: {response_ctx.get('status_code')}\n"
            f"body: {json.dumps(response_ctx.get('body_json'))[:4000]}"
        )
        data = self._generate_json(prompt)
        if not data:
            return self._fallback.suggest_from_response(response_ctx, discovered_checks)
        data.setdefault("suggestions", [])
        return data

    def suggest_negative_cases(self, request_def: dict) -> list[dict]:
        # Reaproveita a heurística determinística: cenários negativos (404/401/400)
        # são estruturais e não se beneficiam de um LLM; mantém consistência e
        # evita custo/latência de chamada ao modelo para algo previsível.
        return self._fallback.suggest_negative_cases(request_def)

    def nl_to_rules(self, text: str, response_ctx: dict | None) -> dict:
        if not self.is_available():
            return self._fallback.nl_to_rules(text, response_ctx)
        body_hint = ""
        if response_ctx and response_ctx.get("json_valid"):
            body_hint = (
                "\n\nResposta REAL observada desta API (use os nomes de campo exatamente como "
                "aparecem aqui - nunca invente um campo que não existe nesta resposta):\n"
                f"{json.dumps(response_ctx.get('body_json'))[:4000]}"
            )
        prompt = (
            "Converta a descrição em português abaixo em regras estruturadas de teste de API. "
            "Operadores válidos: equals, not_equals, contains, starts_with, ends_with, "
            "greater_than, greater_than_or_equal, less_than, less_than_or_equal, matches_regex, "
            "exists, not_exists, type_is, is_email_format. "
            "Se a descrição falar de um subconjunto de uma LISTA (ex: 'clientes PREMIUM'), e essa "
            "lista existir na resposta real, use array_path (caminho da lista), condition_field, "
            "condition_operator ('equals') e condition_expected (o valor que filtra os itens), além "
            "de field/operator/expected relativos a cada item da lista. NUNCA use array_path para uma "
            "condição/valor que não aparece de fato na resposta real. "
            'Responda em JSON: {"rules": [{"field": str, "operator": str, "expected": any, '
            '"array_path": str|null, "condition_field": str|null, "condition_operator": str|null, '
            '"condition_expected": any, "description": str}], "unparsed": [str]}.'
            f"\n\nDescrição: {text}{body_hint}"
        )
        data = self._generate_json(prompt)
        if not data or "rules" not in data:
            return self._fallback.nl_to_rules(text, response_ctx)
        for rule in data["rules"]:
            rule.setdefault("id", "")
            rule.setdefault("source", "ai_suggested")
            rule.setdefault("category", "field")
            rule.setdefault("confidence", 0.6)
        return data

    def answer_question(self, question: str, response_ctx: dict) -> str:
        if not self.is_available() or not response_ctx.get("json_valid"):
            return self._fallback.answer_question(question, response_ctx)
        prompt = (
            "Responda a pergunta abaixo em português, de forma breve e direta, consultando APENAS "
            "os dados reais da resposta JSON fornecida (não invente valores que não estão presentes). "
            "Isto é uma consulta de leitura, não cria nenhum teste.\n\n"
            f"Resposta JSON: {json.dumps(response_ctx.get('body_json'))[:6000]}\n\n"
            f"Pergunta: {question}"
        )
        try:
            resp = httpx.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=20.0,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            return text or self._fallback.answer_question(question, response_ctx)
        except httpx.HTTPError:
            return self._fallback.answer_question(question, response_ctx)

    def suggest_scenarios(self, check: dict) -> list[dict]:
        # Assim como suggest_negative_cases: cenários de valor são derivados
        # deterministicamente do operador/valor da regra, não se beneficiam
        # de um LLM - mantém consistência e evita latência desnecessária.
        return self._fallback.suggest_scenarios(check)

    def explain_failure(self, result: dict, response_ctx: dict | None) -> str:
        if not self.is_available():
            return self._fallback.explain_failure(result, response_ctx)
        prompt = (
            "Explique de forma breve e didática, em português, por que este teste de API falhou, "
            "e sugira 2-3 próximos passos de investigação.\n"
            f"Campo: {result.get('field')}\nOperador: {result.get('operator')}\n"
            f"Esperado: {result.get('expected')}\nObservado: {result.get('actual')}\n"
            f"HTTP status: {(response_ctx or {}).get('status_code')}"
        )
        try:
            resp = httpx.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=20.0,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            return text or self._fallback.explain_failure(result, response_ctx)
        except httpx.HTTPError:
            return self._fallback.explain_failure(result, response_ctx)
