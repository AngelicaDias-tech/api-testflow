"""
Rotas da IA (secao 12-14). Todas retornam SUGESTOES - nenhuma delas
persiste uma Rule sozinha. Persistir uma regra sugerida pela IA exige uma
chamada separada e explicita do usuário para POST /rules ou /rules/bulk
(ver app/api/rules.py), o que garante a aprovacao humana no fluxo.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.ai.factory import get_ai_provider
from app.ai.heuristic_provider import _flatten_field_paths
from app.ai.technical_rule_parser import parse_multiple_lines
from app.core.security import mask_headers
from app.db.database import get_session
from app.db.models import ApiRequestDef, TestResult
from app.schemas import AnswerQuestionIn, GenerateRulesIn, SuggestScenariosIn

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
    ctx = dict(payload.response_ctx)
    ctx["headers"] = mask_headers(ctx.get("headers", {}))
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
    ctx = None
    if payload.response_ctx:
        ctx = dict(payload.response_ctx)
        ctx["headers"] = mask_headers(ctx.get("headers", {}))
    known_fields = _flatten_field_paths(ctx.get("body_json")) if ctx and ctx.get("json_valid") else []
    return parse_multiple_lines(payload.text, known_fields)


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
    ctx = dict(payload.response_ctx)
    ctx["headers"] = mask_headers(ctx.get("headers", {}))
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
