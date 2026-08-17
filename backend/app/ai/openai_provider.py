"""
Provedor de IA opcional via OpenAI (LLM real em nuvem) - unico provider de
LLM real da plataforma (arquitetura: HeuristicAIProvider + OpenAIProvider,
ver app/ai/factory.py). So e usado se o usuario configurar
API_TESTFLOW_AI_PROVIDER=openai E `OPENAI_API_KEY` estiver definida.
Composicao, nao heranca, com fallback automatico para HeuristicAIProvider
- a ausencia ou falha da OpenAI nunca impede o uso da plataforma.

`is_available()` so verifica se a chave foi CONFIGURADA, sem chamada de
rede: a OpenAI e um servico PAGO por chamada, entao testar disponibilidade
fazendo uma requisicao real gastaria creditos a toa a cada
`GET /api/ai/status`. Uma falha real (rede, autenticacao, rate limit) so e
descoberta na hora de uma chamada de verdade, e cai automaticamente para o
fallback heuristico (nunca propaga a excecao para o usuario, e sempre fica
registrada no log tecnico - ver `_log_fallback` - para nunca parecer uma
resposta normal do LLM).

Segredos nunca sao enviados ao modelo (secao 29): os prompts usam apenas
a definicao da requisicao/contexto com headers sensiveis ja mascarados
pelo chamador (ver app/ai/context.py, app/api/ai.py) - a OPENAI_API_KEY em
si tambem nunca faz parte de nenhum prompt/contexto.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.ai.base import AIProvider
from app.ai.heuristic_provider import HeuristicAIProvider
from app.core.config import get_settings

_SYSTEM_PROMPT = (
    "Você é o Assistente de IA do API TestFlow, uma plataforma de testes automatizados de API. "
    "Responda sempre em português, de forma direta e técnica. "
    "Você NUNCA decide se um teste passou ou falhou - essa decisão é sempre do pytest, nunca sua. "
    "Você NUNCA cria uma regra, cenário ou massa de teste sozinho - você só pode SUGERIR; o usuário sempre "
    "revisa e aprova explicitamente antes de qualquer coisa virar um teste real. "
    "Use apenas os dados fornecidos no contexto - nunca invente URL, campo, valor ou resultado que não "
    "esteja presente nele."
)


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._model = settings.openai_model
        self._timeout = settings.openai_timeout_seconds
        self._fallback = HeuristicAIProvider()
        self._client: Any = None

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _client_or_none(self):
        if not self.is_available():
            return None
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key, timeout=self._timeout)
        return self._client

    def _log_fallback(self, method: str, exc: Exception) -> None:
        # Log tecnico explicito (console do servidor) sempre que uma falha
        # REAL da OpenAI causar um fallback - nunca deve parecer uma
        # resposta normal do LLM (requisito de nao mascarar a falha).
        print(  # noqa: T201
            f"[openai_provider] {method}: chamada à OpenAI falhou "
            f"({type(exc).__name__}: {exc}) — usando fallback heurístico."
        )

    def _generate_text(self, prompt: str, *, system: str = _SYSTEM_PROMPT) -> str | None:
        client = self._client_or_none()
        if client is None:
            return None
        try:
            resp = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001 - qualquer falha aqui SEMPRE cai pro fallback, nunca propaga
            self._log_fallback("_generate_text", exc)
            return None

    def _generate_json(self, prompt: str, *, system: str = _SYSTEM_PROMPT) -> dict | None:
        client = self._client_or_none()
        if client is None:
            return None
        try:
            resp = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt + "\n\nResponda em JSON."},
                ],
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content or "{}"
            return json.loads(text)
        except Exception as exc:  # noqa: BLE001
            self._log_fallback("_generate_json", exc)
            return None

    # --- métodos deterministicos: não se beneficiam de um LLM (são derivados
    # mecanicamente do operador/método/URL), então não chamam a OpenAI
    # (evita custo/latência à toa em algo previsível). ---

    def suggest_negative_cases(self, request_def: dict) -> list[dict]:
        return self._fallback.suggest_negative_cases(request_def)

    def suggest_scenarios(self, check: dict) -> list[dict]:
        return self._fallback.suggest_scenarios(check)

    # --- métodos que usam o LLM de verdade -----------------------------------

    def suggest_from_response(self, response_ctx: dict, discovered_checks: list[dict]) -> dict:
        prompt = (
            "Dado o corpo JSON de uma resposta de API abaixo, sugira validações adicionais úteis (não repita "
            'checagens óbvias de tipo/existência). Responda em JSON: {"summary": str, "suggestions": []}, onde '
            'cada suggestion e {"category": str, "field": str, "operator": str, "expected": any, '
            '"description": str}.\n\n'
            f"status_code: {response_ctx.get('status_code')}\n"
            f"body: {json.dumps(response_ctx.get('body_json'))[:4000]}"
        )
        data = self._generate_json(prompt)
        if not data:
            return self._fallback.suggest_from_response(response_ctx, discovered_checks)
        data.setdefault("suggestions", [])
        for s in data["suggestions"]:
            s.setdefault("id", str(uuid.uuid4()))
            s.setdefault("source", "ai_suggested")
        return data

    def nl_to_rules(self, text: str, response_ctx: dict | None) -> dict:
        body_hint = ""
        if response_ctx and response_ctx.get("json_valid"):
            body_hint = (
                "\n\nResposta REAL observada desta API (use os nomes de campo exatamente como aparecem aqui - "
                "nunca invente um campo que não existe nesta resposta):\n"
                f"{json.dumps(response_ctx.get('body_json'))[:4000]}"
            )
        prompt = (
            "Converta a descrição em português abaixo em regras estruturadas de teste de API. "
            "Operadores válidos: equals, not_equals, contains, starts_with, ends_with, greater_than, "
            "greater_than_or_equal, less_than, less_than_or_equal, matches_regex, exists, not_exists, type_is, "
            "is_email_format. Se a descrição falar de um subconjunto de uma LISTA (ex: 'clientes PREMIUM'), e "
            "essa lista existir na resposta real, use array_path (caminho da lista), condition_field, "
            "condition_operator ('equals') e condition_expected (o valor que filtra os itens), além de "
            "field/operator/expected relativos a cada item da lista. NUNCA use array_path para uma "
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
            rule.setdefault("id", str(uuid.uuid4()))
            rule.setdefault("source", "ai_suggested")
            rule.setdefault("category", "field")
            rule.setdefault("confidence", 0.7)
        data.setdefault("unparsed", [])
        return data

    def answer_question(self, question: str, response_ctx: dict) -> str:
        if not response_ctx.get("json_valid"):
            return self._fallback.answer_question(question, response_ctx)
        prompt = (
            "Responda a pergunta abaixo em português, de forma breve e direta, consultando APENAS os dados "
            "reais da resposta JSON fornecida (não invente valores que não estão presentes). Isto é uma "
            "consulta de leitura, não cria nenhum teste.\n\n"
            f"Resposta JSON: {json.dumps(response_ctx.get('body_json'))[:6000]}\n\n"
            f"Pergunta: {question}"
        )
        text = self._generate_text(prompt)
        return text or self._fallback.answer_question(question, response_ctx)

    def explain_failure(self, result: dict, response_ctx: dict | None) -> str:
        prompt = (
            "Explique de forma breve e didática, em português, por que este teste de API falhou, e sugira 2-3 "
            "próximos passos de investigação. Você não decide se o teste passou ou falhou - isso já aconteceu "
            "(o resultado abaixo já veio do pytest); você só explica a causa provável.\n"
            f"Campo: {result.get('field')}\nOperador: {result.get('operator')}\n"
            f"Esperado: {result.get('expected')}\nObservado: {result.get('actual')}\n"
            f"HTTP status: {(response_ctx or {}).get('status_code')}"
        )
        text = self._generate_text(prompt)
        return text or self._fallback.explain_failure(result, response_ctx)

    def chat(self, message: str, context: dict) -> str:
        prompt = f"Contexto: {json.dumps(context, ensure_ascii=False, default=str)[:6000]}\n\nPergunta: {message}"
        text = self._generate_text(prompt)
        return text or self._fallback.chat(message, context)

    def suggest_test_data(self, variables: list[str], response_ctx: dict | None, count: int) -> dict:
        if not variables:
            return self._fallback.suggest_test_data(variables, response_ctx, count)
        body_hint = ""
        if response_ctx and response_ctx.get("json_valid"):
            body_json = json.dumps(response_ctx.get("body_json"))[:3000]
            body_hint = (
                "\n\nResposta real observada desta API (contexto, use para gerar valores plausíveis):\n"
                f"{body_json}"
            )
        prompt = (
            f"Gere {count} casos de teste (massa de dados) para as variáveis: {', '.join(variables)}. "
            "Cada caso deve ter um valor plausível e realista para cada variável (varie os valores entre os "
            "casos, incluindo alguns limites/bordas quando fizer sentido). "
            'Responda em JSON: {"rows": [{"' + variables[0] + '": valor, ...}, ...]} com exatamente '
            f"{count} itens em 'rows'.{body_hint}"
        )
        data = self._generate_json(prompt)
        if not data or "rows" not in data or not isinstance(data["rows"], list) or not data["rows"]:
            return self._fallback.suggest_test_data(variables, response_ctx, count)
        return {"columns": list(variables), "rows": data["rows"][:count]}
