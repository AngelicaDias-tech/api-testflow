from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.database import get_session
from app.db.models import ApiRequestDef, Rule
from app.schemas import RuleBulkCreate, RuleCreate, RuleOut, RuleUpdate

router = APIRouter(prefix="/api/requests/{request_id}/rules", tags=["rules"])


def _get_request_or_404(session: Session, request_id: str) -> ApiRequestDef:
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")
    return req


def _normalize_expected(data: dict) -> dict:
    """`expected`/`condition_expected` chegam como Any (int/bool/str/list) do
    cliente, mas sao persistidos como string - o avaliador
    (app.engine.evaluator) sempre compara via coercao de string/numero,
    entao isso nao perde semantica e evita side-tables so para preservar o
    tipo Python original."""
    for key in ("expected", "condition_expected"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            data[key] = str(data[key])
    return data


@router.get("", response_model=list[RuleOut])
def list_rules(request_id: str, session: Session = Depends(get_session)):
    _get_request_or_404(session, request_id)
    return session.exec(select(Rule).where(Rule.request_id == request_id).order_by(Rule.created_at)).all()


@router.post("", response_model=RuleOut, status_code=201)
def create_rule(request_id: str, payload: RuleCreate, session: Session = Depends(get_session)):
    """Cria uma regra JA APROVADA pelo usuário. A IA nunca chama este
    endpoint sozinha (secao 11/14) - o frontend so o usa depois que o
    usuário clica em 'Adicionar teste'/'Adicionar todos'."""
    _get_request_or_404(session, request_id)
    rule = Rule(request_id=request_id, **_normalize_expected(payload.model_dump()))
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.post("/bulk", response_model=list[RuleOut], status_code=201)
def create_rules_bulk(request_id: str, payload: RuleBulkCreate, session: Session = Depends(get_session)):
    _get_request_or_404(session, request_id)
    created = []
    for item in payload.rules:
        rule = Rule(request_id=request_id, **_normalize_expected(item.model_dump()))
        session.add(rule)
        created.append(rule)
    session.commit()
    for rule in created:
        session.refresh(rule)
    return created


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(request_id: str, rule_id: str, payload: RuleUpdate, session: Session = Depends(get_session)):
    rule = session.get(Rule, rule_id)
    if not rule or rule.request_id != request_id:
        raise HTTPException(404, "Regra não encontrada")
    for key, value in _normalize_expected(payload.model_dump(exclude_unset=True)).items():
        setattr(rule, key, value)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(request_id: str, rule_id: str, session: Session = Depends(get_session)):
    rule = session.get(Rule, rule_id)
    if not rule or rule.request_id != request_id:
        raise HTTPException(404, "Regra não encontrada")
    session.delete(rule)
    session.commit()
