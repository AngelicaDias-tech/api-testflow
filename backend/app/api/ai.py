"""
Rotas da IA (secao 12-14). Todas retornam SUGESTOES - nenhuma delas
persiste uma Rule sozinha. Persistir uma regra sugerida pela IA exige uma
chamada separada e explicita do usuário para POST /rules ou /rules/bulk
(ver app/api/rules.py), o que garante a aprovacao humana no fluxo.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.ai.context import mask_response_ctx
from app.ai.factory import get_ai_provider
from app.ai.heuristic_provider import _flatten_field_paths
from app.ai.technical_rule_parser import parse_multiple_lines
from app.db.database import get_session
from app.db.models import ApiRequestDef, Rule, TestResult
from app.engine.templating import find_placeholders
from app.schemas import (
    AnswerQuestionIn,
    ChatIn,
    GenerateRulesIn,
    NlToRulesIn,
    SuggestScenariosIn,
    SuggestTestDataIn,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])


class SuggestFromResponseIn(BaseModel):
    response_ctx: dict[str, Any]
    discovered_checks: list[dict] = []


@router.get("/status")
def ai_status():
    provider = get_ai_provider()
    return provider.describe()


@router.post("/suggest-from-response")
def suggest_from_response(payload: SuggestFromResponseIn):
    provider = get_ai_provider()
    ctx = mask_response_ctx(payload.response_ctx) or {}
    return provider.suggest_from_response(ctx, payload.discovered_checks)


@router.post("/requests/{request_id}/suggest-negative-cases")
def suggest_negative_cases(request_id: str, session: Session = Depends(get_session)):
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")
    provider = get_ai_provider()
    request_def = {
        "method": req.method,
        "url": req.url,
        "query_params": req.query_params,
        "auth": {"type": (req.auth or {}).get("type", "none")},
    }
    return provider.suggest_negative_cases(request_def)


@router.post("/generate-rules")
def generate_rules(payload: GenerateRulesIn):
    """Função 1 ('Gerar regras'): entrada em sintaxe técnica explícita,
    UMA regra por linha (ex: "stargazers_count > 100"). Determinístico -
    NUNCA interpreta linguagem natural nem tenta adivinhar um campo que
    não existe na resposta real (ver app/ai/technical_rule_parser.py).
    """
    ctx = mask_response_ctx(payload.response_ctx)
    known_fields = _flatten_field_paths(ctx.get("body_json")) if ctx and ctx.get("json_valid") else []
    return parse_multiple_lines(payload.text, known_fields)


@router.post("/nl-to-rules")
def nl_to_rules(payload: NlToRulesIn):
    """Função "Analisar requisito": converte uma frase em PORTUGUÊS livre
    (ex: "Clientes PREMIUM devem estar ativos e ter limite maior que
    1000") em regras estruturadas candidatas, analisando a resposta REAL
    já testada. Diferente de /generate-rules (sintaxe técnica explícita,
    determinística) - aqui a IA de fato interpreta linguagem natural
    (provider.nl_to_rules, ver app/ai/heuristic_provider.py e
    app/ai/openai_provider.py). Como todo endpoint de IA, só retorna
    SUGESTÕES - nada é persistido aqui."""
    provider = get_ai_provider()
    ctx = mask_response_ctx(payload.response_ctx)
    return provider.nl_to_rules(payload.text, ctx)


@router.post("/chat")
def chat(payload: ChatIn):
    """Assistente de IA contextual de propósito geral (melhoria "Assistente
    de IA"): perguntas livres como "explique essa API", "por que esse
    teste falhou", "explique esse 401". `context` já deve chegar montado
    e mascarado pelo chamador (o frontend monta a partir do que está na
    tela - ver AskAssistantComponent). Resposta é sempre só leitura: nunca
    cria uma Rule, nunca decide PASS/FAIL, nunca dispara uma chamada."""
    provider = get_ai_provider()
    ctx = mask_response_ctx(payload.context) or {}
    return {"answer": provider.chat(payload.message, ctx)}


def _collect_known_variables(req: ApiRequestDef, rules: list[Rule]) -> list[str]:
    """Reúne os nomes de variável `{{var}}` já referenciados nesta API - na
    própria definição da requisição (URL/headers/query/body) e no valor
    esperado das regras já aprovadas (ver app.engine.templating). É isso
    que a IA usa para saber QUAIS colunas gerar numa massa - ela nunca
    inventa um nome de variável que a API não usa.

    Quando a API NÃO usa placeholders `{{var}}` (ex: um body com valores
    literais, como `{"title": "...", "price": 3500}`), cai para as
    próprias chaves do JSON do body como candidatas a coluna da massa -
    sem isso, uma API sem nenhum placeholder nunca teria uma massa gerada
    por IA, mesmo tendo um body claramente estruturado para servir de
    modelo (ver Etapa "IA para massas")."""
    names: set[str] = set()
    names |= find_placeholders(req.url)
    names |= find_placeholders(req.body)
    for value in (req.headers or {}).values():
        names |= find_placeholders(value)
    for value in (req.query_params or {}).values():
        names |= find_placeholders(value)
    for rule in rules:
        if isinstance(rule.expected, str):
            names |= find_placeholders(rule.expected)
        if isinstance(rule.condition_expected, str):
            names |= find_placeholders(rule.condition_expected)
    if names:
        return sorted(names)

    if req.body:
        try:
            parsed = json.loads(req.body)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict) and parsed:
            return list(parsed.keys())
    return []


@router.post("/requests/{request_id}/suggest-test-data")
def suggest_test_data(request_id: str, payload: SuggestTestDataIn, session: Session = Depends(get_session)):
    """IA para massas (melhoria "IA para massas"): gera `count` casos
    candidatos para as variáveis `{{var}}` já usadas por esta API/suas
    regras. Devolve o MESMO formato de POST /requests/{id}/datasets/
    preview-csv ({"columns", "rows"}) - o frontend reaproveita a tela de
    prévia/confirmação da massa (app/api/datasets.py), a IA nunca salva
    nem executa nada sozinha."""
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")

    variables = payload.variables
    if not variables:
        rules = session.exec(select(Rule).where(Rule.request_id == request_id)).all()
        variables = _collect_known_variables(req, rules)
    if not variables:
        raise HTTPException(
            400,
            "Não encontrei nenhuma variável {{var}} nem um body em JSON com campos definidos nesta API. "
            "Adicione um placeholder (ex: {{cpf}}) ou um body de exemplo antes de pedir uma massa gerada por IA.",
        )

    provider = get_ai_provider()
    ctx = mask_response_ctx(payload.response_ctx)
    return provider.suggest_test_data(variables, ctx, payload.count)


@router.post("/suggest-scenarios")
def suggest_scenarios(payload: SuggestScenariosIn):
    """Função 2 ('Sugerir cenários'): a partir de uma regra JÁ estruturada,
    sugere 2-3 valores de exemplo com o resultado esperado (PASS/FAIL). A
    IA nunca executa nada - o pytest é quem decide de fato quando/se o
    usuário optar por rodar um desses valores."""
    provider = get_ai_provider()
    return {"scenarios": provider.suggest_scenarios(payload.check)}


@router.post("/answer-question")
def answer_question(payload: AnswerQuestionIn):
    """Consulta/analise em linguagem natural sobre a resposta real (ex:
    'qual o valor do campo elevation?'). Isto NUNCA cria uma Rule nem
    decide PASS/FAIL - e só leitura sobre o JSON observado."""
    provider = get_ai_provider()
    ctx = mask_response_ctx(payload.response_ctx) or {}
    return {"answer": provider.answer_question(payload.question, ctx)}


@router.post("/results/{result_id}/explain")
def explain_failure(result_id: str, session: Session = Depends(get_session)):
    result = session.get(TestResult, result_id)
    if not result:
        raise HTTPException(404, "Resultado não encontrado")

    siblings = session.exec(
        select(TestResult).where(TestResult.execution_id == result.execution_id)
    ).all()
    status_result = next((r for r in siblings if r.field == "$.status_code"), None)
    time_result = next((r for r in siblings if r.field == "$.response_time_ms"), None)

    response_ctx = {}
    if status_result:
        try:
            response_ctx["status_code"] = int(status_result.actual)
        except (TypeError, ValueError):
            pass
    if time_result:
        response_ctx["response_time_ms"] = time_result.actual

    provider = get_ai_provider()
    explanation = provider.explain_failure(
        {
            "field": result.field,
            "operator": result.operator,
            "expected": result.expected,
            "actual": result.actual,
            "category": result.category,
        },
        response_ctx,
    )
    return {"explanation": explanation}
