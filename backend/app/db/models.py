"""
Modelos persistidos em SQLite via SQLModel (secao 24 e 28).

Por que SQLite: zero-config, arquivo unico, gratuito, suficiente para uso
por squad/time. A interface grafica e a forma principal de configuracao;
estas tabelas sao apenas o armazenamento estruturado por baixo dela -
o usuario nunca edita isto diretamente.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Project(SQLModel, table=True):
    """Um projeto/squad (secao 23). Agrupa APIs e testes de um time."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    description: str | None = None
    created_at: datetime = Field(default_factory=_now)


class ApiRequestDef(SQLModel, table=True):
    """
    Definicao de uma requisicao de API testavel (URL + metodo + headers +
    params + body + auth). E o que o usuario cria na tela inicial, seja
    manualmente, via import de cURL ou de Bruno.
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    name: str
    method: str = "GET"
    url: str
    headers: dict = Field(default_factory=dict, sa_column=Column(JSON))
    query_params: dict = Field(default_factory=dict, sa_column=Column(JSON))
    body: str | None = None
    body_type: str = "json"  # json | text | none
    # auth: {"type": "none"|"bearer"|"basic"|"api_key", ...campos especificos}
    # valores sensiveis (token/password/api_key) sao armazenados criptografados.
    auth: dict = Field(default_factory=dict, sa_column=Column(JSON))
    is_mutating: bool = False  # POST/PUT/PATCH/DELETE - exige confirmacao (secao 26)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Ultima resposta observada (para reexibir discovery sem re-chamar a API)
    last_status_code: int | None = None
    last_headers: dict | None = Field(default=None, sa_column=Column(JSON))
    last_body: str | None = None
    last_response_time_ms: float | None = None
    last_probed_at: datetime | None = None


class Rule(SQLModel, table=True):
    """
    Uma expectativa/validacao associada a uma ApiRequestDef: tanto as
    descobertas automaticamente (source=auto) quanto as criadas pelo
    usuario manualmente ou via IA (source=custom), sempre com aprovacao
    explicita do usuario antes de serem persistidas como habilitadas.
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    request_id: str = Field(foreign_key="apirequestdef.id", index=True)
    source: str = "custom"  # auto | custom | ai_suggested
    category: str = "field"  # http | json | field | performance | auth
    field: str | None = None  # dot-path, ex: "data.status" ou None p/ checks globais
    operator: str = "equals"
    expected: str | None = None
    description: str = ""
    enabled: bool = True
    created_at: datetime = Field(default_factory=_now)

    # Regra condicional sobre uma lista (ex: "clientes PREMIUM devem estar
    # ativos"): quando array_path esta preenchido, `field`/`operator`/
    # `expected` acima sao aplicados a CADA elemento do array que satisfizer
    # condition_field/condition_operator/condition_expected. Generico para
    # qualquer API com array de objetos na resposta - opcional/nulo para
    # todas as regras "simples" existentes (retrocompativel).
    array_path: str | None = None
    condition_field: str | None = None
    condition_operator: str | None = None
    condition_expected: str | None = None


class Execution(SQLModel, table=True):
    """Uma rodada de execucao de testes (pytest) para uma ApiRequestDef."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    request_id: str = Field(foreign_key="apirequestdef.id", index=True)
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    duration_ms: float | None = None
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    status: str = "running"  # running | completed | error
    error_message: str | None = None


class TestResult(SQLModel, table=True):
    """
    Um resultado individual dentro de uma Execution, ja mapeado de volta a
    partir do relatorio JSON produzido pelo pytest (pytest e a UNICA
    autoridade de PASS/FAIL - ver secao 15/16).
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    execution_id: str = Field(foreign_key="execution.id", index=True)
    rule_id: str | None = None
    node_id: str = ""
    name: str = ""
    source: str = "custom"  # auto | custom | ai_suggested (copiado da Rule no momento da execucao)
    category: str = "field"
    field: str | None = None
    operator: str | None = None
    expected: str | None = None
    actual: str | None = None
    outcome: str = "failed"  # passed | failed | skipped | error
    message: str | None = None
    duration_ms: float | None = None
