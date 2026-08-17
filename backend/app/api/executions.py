from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api._common import ExecutionRunError, rule_to_check, run_and_persist_execution, to_engine_dict
from app.db.database import get_session
from app.db.models import ApiRequestDef, Execution, Rule, TestResult
from app.schemas import ExecutionOut, ExecutionSummaryOut, SentRequestOut

router = APIRouter(prefix="/api/requests/{request_id}", tags=["executions"])
exec_router = APIRouter(prefix="/api/executions", tags=["executions"])


def execution_to_out(execution: Execution, results: list[TestResult]) -> ExecutionOut:
    """Constroi o ExecutionOut a partir de uma Execution + seus TestResult.
    Existe centralizado aqui (em vez de `ExecutionOut(**execution.model_dump())`
    em cada rota) porque `sent_request_snapshot` (dict cru no banco) precisa
    virar `SentRequestOut` (tipado) - reaproveitado por execute_tests,
    get_execution e pelas rotas novas de cenarios/massas (app/api/scenarios.py,
    app/api/datasets.py), que gravam Execution do mesmo jeito."""
    data = execution.model_dump(exclude={"sent_request_snapshot"})
    sent = execution.sent_request_snapshot
    return ExecutionOut(**data, sent_request=SentRequestOut(**sent) if sent else None, results=results)


@router.post("/execute", response_model=ExecutionOut)
def execute_tests(request_id: str, confirm: bool = False, session: Session = Depends(get_session)):
    """Executa TODAS as regras habilitadas de uma requisicao via pytest de
    verdade (secao 15). Este e o unico caminho que produz PASS/FAIL na
    plataforma - a IA nunca chega perto deste veredito (secao 14)."""
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")
    if req.is_mutating and not confirm:
        raise HTTPException(
            409,
            f"Este teste usa {req.method}, que pode alterar dados reais. Confirme "
            "explicitamente (confirm=true) para executar (secao 26).",
        )

    stmt = select(Rule).where(Rule.request_id == request_id, Rule.enabled == True)  # noqa: E712
    rules = session.exec(stmt).all()
    if not rules:
        raise HTTPException(
            400, "Nenhuma regra habilitada para executar. Adicione validações antes de rodar os testes."
        )

    checks = [rule_to_check(r) for r in rules]
    engine_dict = to_engine_dict(req)

    try:
        execution, results_out = run_and_persist_execution(
            session, request_id, engine_dict, checks, error_context="executar os testes"
        )
    except ExecutionRunError as exc:
        raise HTTPException(500, exc.friendly_message) from exc

    return execution_to_out(execution, results_out)


@router.get("/executions", response_model=list[ExecutionSummaryOut])
def list_executions(request_id: str, session: Session = Depends(get_session)):
    """Historico de execucoes (secao 22)."""
    execs = session.exec(
        select(Execution).where(Execution.request_id == request_id).order_by(Execution.started_at.desc())
    ).all()
    return execs


@exec_router.get("/{execution_id}", response_model=ExecutionOut)
def get_execution(execution_id: str, session: Session = Depends(get_session)):
    execution = session.get(Execution, execution_id)
    if not execution:
        raise HTTPException(404, "Execução não encontrada")
    results = session.exec(select(TestResult).where(TestResult.execution_id == execution_id)).all()
    return execution_to_out(execution, results)
