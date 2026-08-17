"""Pequenos helpers reaproveitados por varias rotas (requests, executions,
scenarios, datasets) - existe para nao triplicar a mesma conversao
ApiRequestDef -> dict "de engine", a mesma lista de metodos mutantes e o
mesmo loop de "rodar pytest e persistir Execution/TestResult" em cada
router novo. Nao e uma camada de servico nova, so evita copia/cola -
pytest continua sendo chamado exatamente como antes
(app.engine.pytest_runner.run_pytest), so o encaixe com o banco foi
centralizado."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session

from app.core.error_messages import internal_error_message
from app.db.models import ApiRequestDef, Execution, Rule, TestResult
from app.engine.http_executor import build_sent_snapshot
from app.engine.pytest_runner import PytestRunError, run_pytest

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class ExecutionRunError(RuntimeError):
    """Erro INTERNO (pytest nao conseguiu rodar) já com a Execution salva
    como 'error' - a rota so precisa transformar isto em HTTPException(500)."""

    def __init__(self, friendly_message: str):
        super().__init__(friendly_message)
        self.friendly_message = friendly_message


def run_and_persist_execution(
    session: Session,
    request_id: str,
    engine_dict: dict,
    checks: list[dict],
    *,
    scenario_id: str | None = None,
    batch_execution_id: str | None = None,
    row_index: int | None = None,
    variables_used: dict | None = None,
    error_context: str = "executar os testes",
) -> tuple[Execution, list[TestResult]]:
    """Roda os `checks` contra `engine_dict` via pytest de verdade e grava
    Execution + TestResult - usado por 'Executar testes' (fluxo original),
    por um cenário manual e por cada linha de uma massa. Levanta
    `ExecutionRunError` se o subprocesso pytest falhar (a Execution já fica
    salva com status='error' antes de propagar)."""
    execution = Execution(
        request_id=request_id,
        status="running",
        scenario_id=scenario_id,
        batch_execution_id=batch_execution_id,
        row_index=row_index,
        variables_used=variables_used,
        sent_request_snapshot=build_sent_snapshot(engine_dict),
    )
    session.add(execution)
    session.commit()
    session.refresh(execution)

    try:
        outcome = run_pytest(engine_dict, checks)
    except PytestRunError as exc:
        print(f"[pytest_runner] falha ao {error_context} (request_id={request_id}): {exc}")  # noqa: T201
        friendly = internal_error_message(error_context)
        execution.status = "error"
        execution.error_message = friendly
        execution.finished_at = datetime.now(UTC)
        session.add(execution)
        session.commit()
        raise ExecutionRunError(friendly) from exc

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

    return execution, results_out


def rule_to_check(rule: Rule) -> dict:
    """Formato de check aceito por app.engine.evaluator/pytest_runner a
    partir de uma Rule persistida - usado por execute_tests, scenarios e
    datasets (todos rodam o MESMO conjunto de regras aprovadas)."""
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


def to_engine_dict(req: ApiRequestDef) -> dict:
    """Formato de request aceito por app.engine.http_executor/pytest_runner:
    o mesmo dict, independente de vir de uma ApiRequestDef direta (fluxo
    original), de um cenario ou de uma linha de massa (ambos aplicam
    app.engine.templating.render_request_def em cima deste dict antes de
    executar)."""
    return {
        "method": req.method,
        "url": req.url,
        "headers": req.headers,
        "query_params": req.query_params,
        "body": req.body,
        "body_type": req.body_type,
        "auth": req.auth,
    }
