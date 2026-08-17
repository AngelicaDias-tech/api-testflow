"""Schemas Pydantic de entrada/saida da API (camada HTTP)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime


class CurlImportIn(BaseModel):
    curl_command: str


class BrunoImportIn(BaseModel):
    bru_content: str


class ImportPreviewOut(BaseModel):
    name: str | None = None
    method: str
    url: str
    headers: dict[str, str]
    query_params: dict[str, str]
    body: str | None
    body_type: str
    auth: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class RequestCreate(BaseModel):
    project_id: str
    name: str
    method: str = "GET"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    body_type: str = "none"
    auth: dict[str, Any] = Field(default_factory=lambda: {"type": "none"})


class RequestUpdate(BaseModel):
    name: str | None = None
    method: str | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    query_params: dict[str, str] | None = None
    body: str | None = None
    body_type: str | None = None
    auth: dict[str, Any] | None = None


class RequestOut(BaseModel):
    id: str
    project_id: str
    name: str
    method: str
    url: str
    headers: dict[str, str]
    query_params: dict[str, str]
    body: str | None
    body_type: str
    auth: dict[str, Any]
    is_mutating: bool
    created_at: datetime
    updated_at: datetime
    last_status_code: int | None
    last_response_time_ms: float | None
    last_probed_at: datetime | None


class SentRequestOut(BaseModel):
    """Request EFETIVAMENTE montado e enviado (melhoria 2) - sempre com
    valores sensiveis mascarados. Ver app.engine.http_executor.build_sent_snapshot."""

    method: str
    url: str
    query_params: dict[str, str]
    headers: dict[str, str]
    auth_type: str
    body: str | None
    body_type: str


class ProbeOut(BaseModel):
    status_code: int | None
    headers: dict[str, str]
    content_type: str
    body_raw: str
    body_json: Any
    json_valid: bool
    response_time_ms: float
    error: str | None
    error_detail: str | None = None
    status_message: str | None = None
    discovered_checks: list[dict]
    sent_request: SentRequestOut | None = None


class RuleCreate(BaseModel):
    source: str = "custom"
    category: str = "field"
    field: str | None = None
    operator: str
    expected: Any = None
    description: str = ""
    enabled: bool = True
    # regra condicional sobre array (opcional - ver app/db/models.py Rule)
    array_path: str | None = None
    condition_field: str | None = None
    condition_operator: str | None = None
    condition_expected: Any = None


class RuleBulkCreate(BaseModel):
    rules: list[RuleCreate]


class RuleOut(BaseModel):
    id: str
    request_id: str
    source: str
    category: str
    field: str | None
    operator: str
    expected: Any
    description: str
    enabled: bool
    created_at: datetime
    array_path: str | None = None
    condition_field: str | None = None
    condition_operator: str | None = None
    condition_expected: str | None = None


class RuleUpdate(BaseModel):
    field: str | None = None
    operator: str | None = None
    expected: Any = None
    description: str | None = None
    enabled: bool | None = None
    array_path: str | None = None
    condition_field: str | None = None
    condition_operator: str | None = None
    condition_expected: Any = None


class GenerateRulesIn(BaseModel):
    """Função 1 ('Gerar regras'): cada linha é sintaxe técnica explícita
    (campo operador valor), nunca linguagem natural."""

    text: str
    response_ctx: dict[str, Any] | None = None


class SuggestScenariosIn(BaseModel):
    """Função 2 ('Sugerir cenários'): parte de uma regra JÁ estruturada
    (field/operator/expected), não de texto livre."""

    check: dict[str, Any]


class AnswerQuestionIn(BaseModel):
    question: str
    response_ctx: dict[str, Any]


class ExplainFailureIn(BaseModel):
    result_id: str


class NlToRulesIn(BaseModel):
    """Função 2 do Assistente de IA ("Analisar requisito"): linguagem
    natural de verdade (ex: "Clientes PREMIUM devem estar ativos"), ao
    contrário de GenerateRulesIn (Função 1, sintaxe técnica explícita)."""

    text: str
    response_ctx: dict[str, Any] | None = None


class ChatIn(BaseModel):
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class SuggestTestDataIn(BaseModel):
    variables: list[str]
    response_ctx: dict[str, Any] | None = None
    count: int = 10


class TestResultOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    execution_id: str
    rule_id: str | None
    node_id: str
    name: str
    source: str
    category: str
    field: str | None
    operator: str | None
    expected: str | None
    actual: str | None
    outcome: str
    message: str | None
    duration_ms: float | None


class ScenarioCreate(BaseModel):
    name: str
    variables: dict[str, Any] = Field(default_factory=dict)


class ScenarioUpdate(BaseModel):
    name: str | None = None
    variables: dict[str, Any] | None = None


class ScenarioOut(BaseModel):
    id: str
    request_id: str
    name: str
    variables: dict[str, Any]
    created_at: datetime


class ExecutionOut(BaseModel):
    id: str
    request_id: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: float | None
    total: int
    passed: int
    failed: int
    skipped: int
    status: str
    error_message: str | None
    scenario_id: str | None = None
    row_index: int | None = None
    variables_used: dict[str, Any] | None = None
    sent_request: SentRequestOut | None = None
    results: list[TestResultOut] = Field(default_factory=list)


class CsvImportPreviewIn(BaseModel):
    csv_text: str


class CsvImportPreviewOut(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    errors: list[str]


class TestDataSetCreate(BaseModel):
    name: str
    columns: list[str]
    rows: list[dict[str, Any]]


class TestDataSetOut(BaseModel):
    id: str
    request_id: str
    name: str
    columns: list[str]
    rows: list[dict[str, Any]]
    created_at: datetime


class BatchExecutionRowOut(BaseModel):
    row_index: int
    variables: dict[str, Any]
    execution_id: str
    outcome: str  # "passed" (0 failed) | "failed" (>=1 failed) | "error"
    total: int
    passed: int
    failed: int


class BatchExecutionOut(BaseModel):
    id: str
    request_id: str
    dataset_id: str
    started_at: datetime
    finished_at: datetime | None
    total_cases: int
    passed_cases: int
    failed_cases: int
    status: str
    rows: list[BatchExecutionRowOut] = Field(default_factory=list)


EXPORT_SCHEMA_VERSION = "1.0"


class ExportAuth(BaseModel):
    """Auth exportada SEM nenhum valor secreto - so o "formato" (tipo,
    nome do header/param, usuario). token/password/api_key nunca aparecem
    aqui (ver app/api/export_import.py:_strip_auth_secrets)."""

    type: str = "none"
    key_name: str | None = None
    location: str | None = None
    username: str | None = None


class ExportRule(BaseModel):
    source: str
    category: str
    field: str | None
    operator: str
    expected: str | None
    description: str
    enabled: bool
    array_path: str | None = None
    condition_field: str | None = None
    condition_operator: str | None = None
    condition_expected: str | None = None


class ExportScenario(BaseModel):
    name: str
    variables: dict[str, Any]


class ExportDataset(BaseModel):
    name: str
    columns: list[str]
    rows: list[dict[str, Any]]


class ExportRequest(BaseModel):
    name: str
    method: str
    url: str
    headers: dict[str, str]  # so headers NAO sensiveis (sensiveis sao omitidos, nao mascarados)
    query_params: dict[str, str]
    body: str | None
    body_type: str
    auth: ExportAuth
    rules: list[ExportRule] = Field(default_factory=list)
    scenarios: list[ExportScenario] = Field(default_factory=list)
    datasets: list[ExportDataset] = Field(default_factory=list)


class ExportProjectMeta(BaseModel):
    name: str
    description: str | None = None


class ExportBundle(BaseModel):
    """Arquivo de exportacao (melhoria "Exportar/Importar testes").
    `testflow_export_version` existe para permitir evoluir o formato (ex:
    adicionar um novo campo) sem quebrar a leitura de arquivos ja
    exportados - ver app/api/export_import.py."""

    testflow_export_version: str = EXPORT_SCHEMA_VERSION
    exported_at: datetime
    project: ExportProjectMeta
    requests: list[ExportRequest] = Field(default_factory=list)


class ImportBundleIn(BaseModel):
    """Mesma estrutura de ExportBundle, mas como entrada (o que o usuario
    envia ao importar) - schemas separados de proposito: o de entrada
    nunca deveria aceitar campos que so fazem sentido na saida, e evolucoes
    futuras de import/export podem divergir sem acoplar os dois lados."""

    testflow_export_version: str
    project: ExportProjectMeta
    requests: list[ExportRequest] = Field(default_factory=list)


class ImportSummaryOut(BaseModel):
    project: ProjectOut
    requests_imported: int
    rules_imported: int
    scenarios_imported: int
    datasets_imported: int
    requests_needing_auth: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExecutionSummaryOut(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: float | None
    total: int
    passed: int
    failed: int
    skipped: int
    status: str
