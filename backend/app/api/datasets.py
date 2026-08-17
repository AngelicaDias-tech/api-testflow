"""
Massas de teste via CSV (melhoria "Massas de teste via CSV" + "Massa +
Request"). Fluxo:

    CSV -> preview (nao persiste) -> confirmar -> TestDataSet (persistido)
    -> executar em lote: cada LINHA vira um Execution normal (mesmo motor
       de app.api.scenarios/executions - render_request_def + render_checks
       + run_pytest via run_and_persist_execution) -> BatchExecution agrega
       o resultado consolidado (total/passou/falhou) sem reimplementar
       nada do motor de avaliacao.

Formato inicial: CSV (app/engine/csv_import.py). A estrutura de
TestDataSet (columns+rows como JSON) ja e format-agnostica o bastante para
um importador de JSON futuro reaproveitar o mesmo modelo/rotas de
execucao, sem precisar de uma segunda arquitetura de massa.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api._common import (
    MUTATING_METHODS,
    ExecutionRunError,
    rule_to_check,
    run_and_persist_execution,
    to_engine_dict,
)
from app.db.database import get_session
from app.db.models import ApiRequestDef, BatchExecution, Execution, Rule, TestDataSet
from app.engine.csv_import import CsvImportError, parse_csv
from app.engine.templating import render_checks, render_request_def
from app.schemas import (
    BatchExecutionOut,
    BatchExecutionRowOut,
    CsvImportPreviewIn,
    CsvImportPreviewOut,
    TestDataSetCreate,
    TestDataSetOut,
)

router = APIRouter(prefix="/api/requests/{request_id}/datasets", tags=["datasets"])
batch_router = APIRouter(prefix="/api/batch-executions", tags=["datasets"])


def _get_request_or_404(session: Session, request_id: str) -> ApiRequestDef:
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")
    return req


def _get_dataset_or_404(session: Session, request_id: str, dataset_id: str) -> TestDataSet:
    dataset = session.get(TestDataSet, dataset_id)
    if not dataset or dataset.request_id != request_id:
        raise HTTPException(404, "Massa de teste não encontrada")
    return dataset


@router.post("/preview-csv", response_model=CsvImportPreviewOut)
def preview_csv(request_id: str, payload: CsvImportPreviewIn, session: Session = Depends(get_session)):
    """Passo 1: só faz parsing/validação e devolve uma prévia — nada é
    salvo ainda (mesmo padrão de app/api/imports.py para cURL/Bruno)."""
    _get_request_or_404(session, request_id)
    try:
        result = parse_csv(payload.csv_text)
    except CsvImportError as exc:
        raise HTTPException(400, str(exc)) from exc
    return CsvImportPreviewOut(**result)


@router.get("", response_model=list[TestDataSetOut])
def list_datasets(request_id: str, session: Session = Depends(get_session)):
    _get_request_or_404(session, request_id)
    stmt = select(TestDataSet).where(TestDataSet.request_id == request_id).order_by(TestDataSet.created_at)
    return session.exec(stmt).all()


@router.post("", response_model=TestDataSetOut, status_code=201)
def create_dataset(request_id: str, payload: TestDataSetCreate, session: Session = Depends(get_session)):
    """Passo 2: confirma a prévia e persiste a massa. Exige que o usuário
    já tenha revisto `rows`/`errors` da prévia (o frontend só chama isto
    depois da confirmação explícita)."""
    _get_request_or_404(session, request_id)
    if not payload.rows:
        raise HTTPException(400, "A massa não tem nenhuma linha válida para salvar.")
    dataset = TestDataSet(request_id=request_id, name=payload.name, columns=payload.columns, rows=payload.rows)
    session.add(dataset)
    session.commit()
    session.refresh(dataset)
    return dataset


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(request_id: str, dataset_id: str, session: Session = Depends(get_session)):
    dataset = _get_dataset_or_404(session, request_id, dataset_id)
    session.delete(dataset)
    session.commit()


def _batch_to_out(batch: BatchExecution, rows_out: list[BatchExecutionRowOut]) -> BatchExecutionOut:
    data = batch.model_dump()
    return BatchExecutionOut(**data, rows=rows_out)


@router.post("/{dataset_id}/execute", response_model=BatchExecutionOut)
def execute_dataset(
    request_id: str, dataset_id: str, confirm: bool = False, session: Session = Depends(get_session)
):
    """Executa TODOS os casos da massa, um de cada vez (sequencial), contra
    as regras já aprovadas da API. Cada linha vira um Execution normal
    (mesmo histórico/detalhe de sempre) e o BatchExecution só agrega o
    resultado - PASS/FAIL de cada caso continua vindo exclusivamente do
    pytest, executado uma vez por linha."""
    req = _get_request_or_404(session, request_id)
    dataset = _get_dataset_or_404(session, request_id, dataset_id)

    if req.method.upper() in MUTATING_METHODS and not confirm:
        raise HTTPException(
            409,
            f"Esta massa tem {len(dataset.rows)} caso(s) e usa {req.method}, que pode alterar dados reais — "
            f"isso disparará até {len(dataset.rows)} chamadas reais. Confirme explicitamente (confirm=true) "
            "para executar mesmo assim.",
        )

    stmt = select(Rule).where(Rule.request_id == request_id, Rule.enabled == True)  # noqa: E712
    rules = session.exec(stmt).all()
    if not rules:
        raise HTTPException(
            400, "Nenhuma regra habilitada para executar. Adicione validações antes de rodar a massa."
        )
    checks_template = [rule_to_check(r) for r in rules]
    base_engine_dict = to_engine_dict(req)

    batch = BatchExecution(request_id=request_id, dataset_id=dataset_id, status="running")
    session.add(batch)
    session.commit()
    session.refresh(batch)

    rows_out: list[BatchExecutionRowOut] = []
    passed_cases = 0
    failed_cases = 0
    for idx, row_vars in enumerate(dataset.rows):
        engine_dict = render_request_def(base_engine_dict, row_vars)
        checks = render_checks(checks_template, row_vars)
        try:
            execution, _results = run_and_persist_execution(
                session,
                request_id,
                engine_dict,
                checks,
                batch_execution_id=batch.id,
                row_index=idx,
                variables_used=row_vars,
                error_context=f"executar o caso {idx + 1} da massa",
            )
        except ExecutionRunError:
            # A Execution já ficou salva como status='error' — o caso conta
            # como falho no resumo consolidado, mas a massa inteira segue
            # para os próximos casos (um caso com erro interno não deve
            # travar os demais).
            failed_cases += 1
            rows_out.append(
                BatchExecutionRowOut(
                    row_index=idx,
                    variables=row_vars,
                    execution_id="",
                    outcome="error",
                    total=0,
                    passed=0,
                    failed=0,
                )
            )
            continue

        case_outcome = "passed" if execution.failed == 0 else "failed"
        if case_outcome == "passed":
            passed_cases += 1
        else:
            failed_cases += 1
        rows_out.append(
            BatchExecutionRowOut(
                row_index=idx,
                variables=row_vars,
                execution_id=execution.id,
                outcome=case_outcome,
                total=execution.total,
                passed=execution.passed,
                failed=execution.failed,
            )
        )

    batch.status = "completed"
    batch.finished_at = datetime.now(UTC)
    batch.total_cases = len(dataset.rows)
    batch.passed_cases = passed_cases
    batch.failed_cases = failed_cases
    session.add(batch)
    session.commit()
    session.refresh(batch)

    return _batch_to_out(batch, rows_out)


def _rows_out_for_batch(session: Session, batch: BatchExecution) -> list[BatchExecutionRowOut]:
    executions = session.exec(
        select(Execution).where(Execution.batch_execution_id == batch.id).order_by(Execution.row_index)
    ).all()
    rows_out = []
    for execution in executions:
        outcome = "error" if execution.status == "error" else ("passed" if execution.failed == 0 else "failed")
        rows_out.append(
            BatchExecutionRowOut(
                row_index=execution.row_index if execution.row_index is not None else -1,
                variables=execution.variables_used or {},
                execution_id=execution.id,
                outcome=outcome,
                total=execution.total,
                passed=execution.passed,
                failed=execution.failed,
            )
        )
    return rows_out


@batch_router.get("/{batch_id}", response_model=BatchExecutionOut)
def get_batch_execution(batch_id: str, session: Session = Depends(get_session)):
    batch = session.get(BatchExecution, batch_id)
    if not batch:
        raise HTTPException(404, "Execução de massa não encontrada")
    return _batch_to_out(batch, _rows_out_for_batch(session, batch))


@router.get("/{dataset_id}/executions", response_model=list[BatchExecutionOut])
def list_batch_executions(request_id: str, dataset_id: str, session: Session = Depends(get_session)):
    """Histórico de rodadas em lote desta massa (mesmo espírito de
    GET /requests/{id}/executions para o fluxo original)."""
    _get_dataset_or_404(session, request_id, dataset_id)
    stmt = (
        select(BatchExecution)
        .where(BatchExecution.dataset_id == dataset_id)
        .order_by(BatchExecution.started_at.desc())
    )
    batches = session.exec(stmt).all()
    return [_batch_to_out(b, _rows_out_for_batch(session, b)) for b in batches]
