from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.security import (
    carry_over_blank_secrets,
    encrypt_auth_for_storage,
    encrypt_headers_for_storage,
    is_sensitive_auth_field,
    is_sensitive_header,
    mask_auth,
    mask_headers,
)
from app.db.database import get_session
from app.db.models import ApiRequestDef
from app.engine.discovery import discover_checks
from app.engine.http_executor import execute_request
from app.schemas import ProbeOut, RequestCreate, RequestOut, RequestUpdate

router = APIRouter(prefix="/api/requests", tags=["requests"])

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _to_out(req: ApiRequestDef) -> RequestOut:
    return RequestOut(
        id=req.id,
        project_id=req.project_id,
        name=req.name,
        method=req.method,
        url=req.url,
        headers=mask_headers(req.headers),
        query_params=req.query_params,
        body=req.body,
        body_type=req.body_type,
        auth=mask_auth(req.auth) or {"type": "none"},
        is_mutating=req.is_mutating,
        created_at=req.created_at,
        updated_at=req.updated_at,
        last_status_code=req.last_status_code,
        last_response_time_ms=req.last_response_time_ms,
        last_probed_at=req.last_probed_at,
    )


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


@router.get("", response_model=list[RequestOut])
def list_requests(project_id: str = Query(...), session: Session = Depends(get_session)):
    stmt = (
        select(ApiRequestDef)
        .where(ApiRequestDef.project_id == project_id)
        .order_by(ApiRequestDef.created_at.desc())
    )
    reqs = session.exec(stmt).all()
    return [_to_out(r) for r in reqs]


@router.post("", response_model=RequestOut, status_code=201)
def create_request(payload: RequestCreate, session: Session = Depends(get_session)):
    req = ApiRequestDef(
        project_id=payload.project_id,
        name=payload.name,
        method=payload.method.upper(),
        url=payload.url,
        headers=encrypt_headers_for_storage(payload.headers),
        query_params=payload.query_params,
        body=payload.body,
        body_type=payload.body_type,
        auth=encrypt_auth_for_storage(payload.auth),
        is_mutating=payload.method.upper() in _MUTATING_METHODS,
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    return _to_out(req)


@router.get("/{request_id}", response_model=RequestOut)
def get_request(request_id: str, session: Session = Depends(get_session)):
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")
    return _to_out(req)


@router.put("/{request_id}", response_model=RequestOut)
def update_request(request_id: str, payload: RequestUpdate, session: Session = Depends(get_session)):
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")
    data = payload.model_dump(exclude_unset=True)
    if "headers" in data:
        encrypted_headers = encrypt_headers_for_storage(data["headers"])
        data["headers"] = carry_over_blank_secrets(encrypted_headers, req.headers, is_sensitive_header)
    if "auth" in data:
        encrypted_auth = encrypt_auth_for_storage(data["auth"])
        data["auth"] = carry_over_blank_secrets(encrypted_auth, req.auth, is_sensitive_auth_field)
    if "method" in data:
        data["method"] = data["method"].upper()
        data["is_mutating"] = data["method"] in _MUTATING_METHODS
    for key, value in data.items():
        setattr(req, key, value)
    req.updated_at = datetime.now(UTC)
    session.add(req)
    session.commit()
    session.refresh(req)
    return _to_out(req)


@router.delete("/{request_id}", status_code=204)
def delete_request(request_id: str, session: Session = Depends(get_session)):
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")
    session.delete(req)
    session.commit()


@router.post("/{request_id}/probe", response_model=ProbeOut)
def probe_request(request_id: str, confirm: bool = False, session: Session = Depends(get_session)):
    """Executa a requisicao AGORA e captura status/headers/body/tempo,
    retornando tambem as validacoes tecnicas descobertas automaticamente
    (secao 7/8). Metodos mutantes (POST/PUT/PATCH/DELETE) exigem
    confirm=true explicito - GET/HEAD/OPTIONS podem rodar direto
    (secao 26)."""
    req = session.get(ApiRequestDef, request_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada")
    if req.is_mutating and not confirm:
        raise HTTPException(
            409,
            f"Este teste usa {req.method}, que pode alterar dados. Confirme explicitamente "
            "(confirm=true) para executar de verdade.",
        )

    ctx = execute_request(_to_engine_dict(req), timeout=15.0)
    if ctx.get("error"):
        raise HTTPException(502, f"Falha ao chamar a API: {ctx['error']}")

    req.last_status_code = ctx["status_code"]
    req.last_headers = ctx["headers"]
    req.last_body = ctx["body_raw"][:200_000]
    req.last_response_time_ms = ctx["response_time_ms"]
    req.last_probed_at = datetime.now(UTC)
    session.add(req)
    session.commit()

    discovered = discover_checks(ctx)
    return ProbeOut(
        status_code=ctx["status_code"],
        headers=mask_headers(ctx["headers"]),
        content_type=ctx["content_type"],
        body_raw=ctx["body_raw"],
        body_json=ctx["body_json"],
        json_valid=ctx["json_valid"],
        response_time_ms=ctx["response_time_ms"],
        error=ctx["error"],
        discovered_checks=discovered,
    )
