"""
Exportar/Importar testes (melhoria "Exportar/Importar testes"). Unidade de
exportacao e o PROJETO inteiro: nome, cada API testada (metodo/URL/
headers/params/body/auth), suas regras, cenarios e massas de teste.

Regra de seguranca inegociavel: nenhum valor secreto (token/senha/api_key,
e qualquer header sensivel como Authorization/Cookie) sai no arquivo, nem
mascarado, nem criptografado - so o "formato" (tipo de auth, nome do
header/param). Quem importa precisa preencher o segredo de novo em
"Editar API" antes de testar de verdade. Ver app.core.security para a
lista de nomes considerados sensiveis (mesma usada em toda a plataforma).

`testflow_export_version` (app/schemas.py) existe para o formato poder
evoluir (ex: um novo campo em uma versao futura) sem quebrar a leitura de
arquivos ja exportados por uma versao anterior.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.security import encrypt_auth_for_storage, encrypt_headers_for_storage, is_sensitive_header
from app.db.database import get_session
from app.db.models import ApiRequestDef, Project, Rule, Scenario, TestDataSet
from app.schemas import (
    EXPORT_SCHEMA_VERSION,
    ExportAuth,
    ExportBundle,
    ExportDataset,
    ExportProjectMeta,
    ExportRequest,
    ExportRule,
    ExportScenario,
    ImportBundleIn,
    ImportSummaryOut,
    ProjectOut,
)

router = APIRouter(prefix="/api/projects", tags=["export-import"])

_SUPPORTED_MAJOR_VERSION = "1"


def _strip_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in (headers or {}).items() if not is_sensitive_header(k)}


def _strip_auth_secrets(auth: dict | None) -> ExportAuth:
    """`key_name`/`location`/`username` sao METADADOS (nome de header/param,
    local, usuario) - nunca segredos por si so. `token`/`password`/
    `api_key` (ver app.core.security._SENSITIVE_AUTH_FIELDS) sao os UNICOS
    campos de auth com valor secreto, e sao deliberadamente omitidos aqui
    (nem sequer mascarados) - o dict de saida (ExportAuth) nem tem esses
    campos no schema, entao omiti-los e a unica opcao possivel."""
    auth = auth or {}
    return ExportAuth(
        type=auth.get("type", "none"),
        key_name=auth.get("key_name"),
        location=auth.get("location"),
        username=auth.get("username"),
    )


@router.get("/{project_id}/export", response_model=ExportBundle)
def export_project(project_id: str, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Projeto não encontrado")

    reqs = session.exec(select(ApiRequestDef).where(ApiRequestDef.project_id == project_id)).all()

    export_requests: list[ExportRequest] = []
    for req in reqs:
        rules = session.exec(select(Rule).where(Rule.request_id == req.id)).all()
        scenarios = session.exec(select(Scenario).where(Scenario.request_id == req.id)).all()
        datasets = session.exec(select(TestDataSet).where(TestDataSet.request_id == req.id)).all()

        export_requests.append(
            ExportRequest(
                name=req.name,
                method=req.method,
                url=req.url,
                headers=_strip_sensitive_headers(req.headers),
                query_params=req.query_params,
                body=req.body,
                body_type=req.body_type,
                auth=_strip_auth_secrets(req.auth),
                rules=[
                    ExportRule(
                        source=r.source,
                        category=r.category,
                        field=r.field,
                        operator=r.operator,
                        expected=r.expected,
                        description=r.description,
                        enabled=r.enabled,
                        array_path=r.array_path,
                        condition_field=r.condition_field,
                        condition_operator=r.condition_operator,
                        condition_expected=r.condition_expected,
                    )
                    for r in rules
                ],
                scenarios=[ExportScenario(name=s.name, variables=s.variables) for s in scenarios],
                datasets=[ExportDataset(name=d.name, columns=d.columns, rows=d.rows) for d in datasets],
            )
        )

    return ExportBundle(
        testflow_export_version=EXPORT_SCHEMA_VERSION,
        exported_at=datetime.now(UTC),
        project=ExportProjectMeta(name=project.name, description=project.description),
        requests=export_requests,
    )


@router.post("/import", response_model=ImportSummaryOut, status_code=201)
def import_project(payload: ImportBundleIn, session: Session = Depends(get_session)):
    """Cria um PROJETO NOVO a partir do arquivo importado (nunca sobrescreve
    um projeto existente) - o usuário revisa/renomeia depois se quiser.
    Segredos nunca são restaurados automaticamente (não estavam no
    arquivo); requests que precisam de autenticação ficam listados em
    `requests_needing_auth` para o usuário preencher antes de testar."""
    major_version = payload.testflow_export_version.split(".")[0]
    if major_version != _SUPPORTED_MAJOR_VERSION:
        raise HTTPException(
            400,
            f"Versão de exportação não suportada ({payload.testflow_export_version}). "
            f"Este TestFlow lê arquivos na versão {EXPORT_SCHEMA_VERSION}.x.",
        )

    project = Project(name=payload.project.name, description=payload.project.description)
    session.add(project)
    session.commit()
    session.refresh(project)

    rules_count = 0
    scenarios_count = 0
    datasets_count = 0
    requests_needing_auth: list[str] = []

    for exp_req in payload.requests:
        req = ApiRequestDef(
            project_id=project.id,
            name=exp_req.name,
            method=exp_req.method.upper(),
            url=exp_req.url,
            headers=encrypt_headers_for_storage(exp_req.headers),
            query_params=exp_req.query_params,
            body=exp_req.body,
            body_type=exp_req.body_type,
            auth=encrypt_auth_for_storage(exp_req.auth.model_dump(exclude_none=True)),
            is_mutating=exp_req.method.upper() in {"POST", "PUT", "PATCH", "DELETE"},
        )
        session.add(req)
        session.commit()
        session.refresh(req)

        if exp_req.auth.type != "none":
            requests_needing_auth.append(exp_req.name)

        for exp_rule in exp_req.rules:
            session.add(Rule(request_id=req.id, **exp_rule.model_dump()))
            rules_count += 1
        for exp_scenario in exp_req.scenarios:
            session.add(Scenario(request_id=req.id, name=exp_scenario.name, variables=exp_scenario.variables))
            scenarios_count += 1
        for exp_dataset in exp_req.datasets:
            session.add(
                TestDataSet(
                    request_id=req.id, name=exp_dataset.name, columns=exp_dataset.columns, rows=exp_dataset.rows
                )
            )
            datasets_count += 1
        session.commit()

    warnings = []
    if requests_needing_auth:
        warnings.append(
            "As seguintes APIs importadas precisam de autenticação, que não é restaurada automaticamente "
            "por segurança — configure em 'Editar API' antes de testar: " + ", ".join(requests_needing_auth)
        )

    return ImportSummaryOut(
        project=ProjectOut(
            id=project.id, name=project.name, description=project.description, created_at=project.created_at
        ),
        requests_imported=len(payload.requests),
        rules_imported=rules_count,
        scenarios_imported=scenarios_count,
        datasets_imported=datasets_count,
        requests_needing_auth=requests_needing_auth,
        warnings=warnings,
    )
