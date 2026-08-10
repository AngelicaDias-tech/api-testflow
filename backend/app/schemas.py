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


class ProbeOut(BaseModel):
    status_code: int | None
    headers: dict[str, str]
    content_type: str
    body_raw: str
    body_json: Any
    json_valid: bool
    response_time_ms: float
    error: str | None
    discovered_checks: list[dict]


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
    results: list[TestResultOut] = Field(default_factory=list)


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
