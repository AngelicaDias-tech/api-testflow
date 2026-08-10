from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.database import get_session
from app.db.models import ApiRequestDef, Execution, Rule, TestResult
from app.engine.pytest_runner import PytestRunError, run_pytest
from app.schemas import ExecutionOut, ExecutionSummaryOut

router = APIRouter(prefix="/api/requests/{request_id}", tags=["executions"])
exec_router = APIRouter(prefix="/api/executions", tags=["executions"])


def _rule_to_check(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "source": rule.source,
        "category": rule.category,
        "field": rule.field,
        "operator": rule.operator,
        "expected": rule.expected,
        "description": rule.description,
        "array_path": rule.array_path,
        "condition_field": rule.condition_field,
        "condition_operator": rule.condition_operator,
        "condition_expected": rule.condition_expected,
    }


def _to_engine_dict(req: ApiRequestDef) -> dict:
    return {
        "method": req.method,
        "url": req.url,
        "headers": req.headers,
        "query_params": req.query_params,
        "body": req.body,
        "body_type": req.body_type,
        "auth": req.auth,
    }


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

    checks = [_rule_to_check(r) for r in rules]

    execution = Execution(request_id=request_id, status="running")
    session.add(execution)
    session.commit()
    session.refresh(execution)

    try:
        outcome = run_pytest(_to_engine_dict(req), checks)
    except PytestRunError as exc:
        execution.status = "error"
        execution.error_message = str(exc)
        execution.finished_at = datetime.now(UTC)
        session.add(execution)
        session.commit()
        raise HTTPException(500, f"Falha ao executar pytest: {exc}") from exc

    summary = outcome["summary"]
    execution.status = "completed"
    execution.finished_at = datetime.now(UTC)
    execution.duration_ms = summary["duration_ms"]
    execution.total = summary["total"]
    execution.passed = summary["passed"]
    execution.failed = summary["failed"]
    execution.skipped = summary["skipped"]
    session.add(execution)

    results_out = []
    for r in outcome["results"]:
        result = TestResult(
            execution_id=execution.id,
            rule_id=r["rule_id"],
            node_id=r["node_id"],
            name=r["name"],
            source=r["source"] or "custom",
            category=r["category"] or "field",
            field=r["field"],
            operator=r["operator"],
            expected=r["expected"],
            actual=r["actual"],
            outcome=r["outcome"],
            message=r["message"],
            duration_ms=r["duration_ms"],
        )
        session.add(result)
        results_out.append(result)
    session.commit()
    for r in results_out:
        session.refresh(r)
    session.refresh(execution)

    return ExecutionOut(**execution.model_dump(), results=results_out)


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
    return ExecutionOut(**execution.model_dump(), results=results)
