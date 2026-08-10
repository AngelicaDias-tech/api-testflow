from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.engine.bruno_import import BrunoParseError, parse_bru
from app.engine.curl_import import CurlParseError, parse_curl
from app.schemas import BrunoImportIn, CurlImportIn, ImportPreviewOut

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/curl", response_model=ImportPreviewOut)
def import_curl(payload: CurlImportIn):
    """Converte um comando cURL em uma definicao de requisicao para o
    usuario REVISAR antes de salvar/executar (secao 5) - nada e persistido
    aqui ainda."""
    try:
        parsed = parse_curl(payload.curl_command)
    except CurlParseError as exc:
        raise HTTPException(400, str(exc)) from exc
    return ImportPreviewOut(name="Importado via cURL", **parsed, warnings=[])


@router.post("/bruno", response_model=ImportPreviewOut)
def import_bruno(payload: BrunoImportIn):
    """Converte um arquivo `.bru` (requisicao unica do Bruno) em uma
    definicao de requisicao para revisao (secao 6)."""
    try:
        parsed = parse_bru(payload.bru_content)
    except BrunoParseError as exc:
        raise HTTPException(400, str(exc)) from exc
    unresolved = parsed.pop("unresolved_variables", [])
    warnings = []
    if unresolved:
        warnings.append(
            "Esta requisição usa variáveis do Bruno ({{"
            + "}}, {{".join(unresolved)
            + "}}) que não foram resolvidas automaticamente (importação de "
            "environments/collections completas do Bruno ainda não é suportada). "
            "Substitua-as manualmente antes de testar."
        )
    return ImportPreviewOut(**parsed, warnings=warnings)
