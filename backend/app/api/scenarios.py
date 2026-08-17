"""
Cenarios de teste manuais (melhoria "Cenarios de Teste"): um conjunto
nomeado de variaveis (ex: cpf/idade/valor) que preenche os placeholders
`{{var}}` da ApiRequestDef só na hora de executar, sem alterar a
configuracao original da API salva. Fluxo:

    cenario (variaveis) -> render_request_def -> execute_request (via
    run_pytest, MESMO motor de sempre) -> regras ja aprovadas -> PASS/FAIL

Nao ha um segundo motor de avaliacao: um cenario so prepara o
`request_def`/`checks` de entrada e reaproveita exatamente
app.engine.pytest_runner.run_pytest - pytest continua sendo a UNICA
autoridade de PASS/FAIL.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api._common import (
    MUTATING_METHODS,
    ExecutionRunError,
    rule_to_check,
    run_and_persist_execution,
    to_engine_dict,
)
from app.api.executions import execution_to_out
from app.db.database import get_session
from app.db.models import ApiRequestDef, Rule, Scenario
from app.engine.templating import render_checks, render_request_def
from app.schemas import ExecutionOut, ScenarioCreate, ScenarioOut, ScenarioUpdate

router = APIRouter(prefix="/api/requests/{request_id}/scenarios", tags=["scenarios"])


def _get_request_or_404(session: Session, request_id: str) -> ApiRequestDef:
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")
    return req


def _get_scenario_or_404(session: Session, request_id: str, scenario_id: str) -> Scenario:
    scenario = session.get(Scenario, scenario_id)
    if not scenario or scenario.request_id != request_id:
        raise HTTPException(404, "Cenário não encontrado")
    return scenario


@router.get("", response_model=list[ScenarioOut])
def list_scenarios(request_id: str, session: Session = Depends(get_session)):
    _get_request_or_404(session, request_id)
    stmt = select(Scenario).where(Scenario.request_id == request_id).order_by(Scenario.created_at)
    return session.exec(stmt).all()


@router.post("", response_model=ScenarioOut, status_code=201)
def create_scenario(request_id: str, payload: ScenarioCreate, session: Session = Depends(get_session)):
    _get_request_or_404(session, request_id)
    scenario = Scenario(request_id=request_id, name=payload.name, variables=payload.variables)
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    return scenario


@router.put("/{scenario_id}", response_model=ScenarioOut)
def update_scenario(
    request_id: str, scenario_id: str, payload: ScenarioUpdate, session: Session = Depends(get_session)
):
    scenario = _get_scenario_or_404(session, request_id, scenario_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(scenario, key, value)
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    return scenario


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(request_id: str, scenario_id: str, session: Session = Depends(get_session)):
    scenario = _get_scenario_or_404(session, request_id, scenario_id)
    session.delete(scenario)
    session.commit()


@router.post("/{scenario_id}/execute", response_model=ExecutionOut)
def execute_scenario(
    request_id: str, scenario_id: str, confirm: bool = False, session: Session = Depends(get_session)
):
    """Roda ESTE cenario contra a API real e avalia as regras já aprovadas
    da requisição (as mesmas usadas por 'Executar testes') - nunca altera a
    ApiRequestDef original no banco, só o request_def em memória usado
    nesta chamada."""
    req = _get_request_or_404(session, request_id)
    scenario = _get_scenario_or_404(session, request_id, scenario_id)

    if req.method.upper() in MUTATING_METHODS and not confirm:
        raise HTTPException(
            409,
            f"Este cenário usa {req.method}, que pode alterar dados reais. Confirme explicitamente "
            "(confirm=true) para executar de verdade.",
        )

    stmt = select(Rule).where(Rule.request_id == request_id, Rule.enabled == True)  # noqa: E712
    rules = session.exec(stmt).all()
    if not rules:
        raise HTTPException(
            400, "Nenhuma regra habilitada para executar. Adicione validações antes de rodar os cenários."
        )

    variables = scenario.variables or {}
    engine_dict = render_request_def(to_engine_dict(req), variables)
    checks = render_checks([rule_to_check(r) for r in rules], variables)

    try:
        execution, results_out = run_and_persist_execution(
            session,
            request_id,
            engine_dict,
            checks,
            scenario_id=scenario.id,
            variables_used=variables,
            error_context="executar o cenário",
        )
    except ExecutionRunError as exc:
        raise HTTPException(500, exc.friendly_message) from exc

    return execution_to_out(execution, results_out)
