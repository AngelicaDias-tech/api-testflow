"""
Motor de descoberta automatica (secao 8 e 9 do spec).

Por que existe: a plataforma e universal - nao conhece a API do usuario
de antemao. Este modulo olha para UMA resposta real e gera checks
puramente TECNICOS e OBSERVAVEIS (json valido, campo existe, campo tem
tipo X, formato plausivel de email/URL/data, tempo de resposta).

Ele NUNCA gera uma regra de VALOR de negocio (ex: "status == ACTIVE").
Isso e responsabilidade do usuario (secao 10) ou de uma sugestao explicita
da IA que o usuario precisa aprovar (secao 11). A unica excecao tecnica e o
codigo HTTP: assumimos que o codigo observado e o "contrato" atual da API
(uma checagem de regressao tecnica, nao uma regra de dominio), da mesma
forma que "id e integer" observa um tipo, nao um valor de negocio.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://[^\s]+$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}:\d{2})?")

_MAX_FIELDS = 40  # evita explosao de checks em respostas gigantes
_MAX_DEPTH = 2


def _check(category: str, field: str | None, operator: str, expected: Any, description: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "source": "auto",
        "category": category,
        "field": field,
        "operator": operator,
        "expected": expected,
        "description": description,
        "enabled": True,
    }


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _format_checks_for_string(field_path: str, value: str) -> list[dict]:
    checks = []
    if _EMAIL_RE.match(value):
        checks.append(
            _check("field", field_path, "is_email_format", None, f"{field_path} possui formato plausível de email")
        )
    elif _URL_RE.match(value):
        checks.append(
            _check("field", field_path, "matches_regex", r"^https?://", f"{field_path} possui formato de URL")
        )
    elif _UUID_RE.match(value):
        checks.append(
            _check(
                "field",
                field_path,
                "matches_regex",
                _UUID_RE.pattern,
                f"{field_path} possui formato de UUID",
            )
        )
    elif _DATE_RE.match(value):
        checks.append(
            _check(
                "field", field_path, "matches_regex", _DATE_RE.pattern, f"{field_path} possui formato de data/hora"
            )
        )
    return checks


def _walk(obj: Any, prefix: str, depth: int, out: list[dict]) -> None:
    if len(out) >= _MAX_FIELDS or depth > _MAX_DEPTH:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if len(out) >= _MAX_FIELDS:
                return
            field_path = f"{prefix}.{key}" if prefix else key
            value_type = _type_name(value)
            out.append(_check("field", field_path, "exists", None, f"{field_path} existe"))
            out.append(_check("field", field_path, "type_is", value_type, f"{field_path} é {value_type}"))
            if isinstance(value, str) and value:
                out.extend(_format_checks_for_string(field_path, value))
            if isinstance(value, dict | list):
                _walk(value, field_path, depth + 1, out)
    elif isinstance(obj, list) and obj:
        # amostra o primeiro item para nao gerar um check por elemento do array
        sample_path = f"{prefix}.0" if prefix else "0"
        out.append(_check("field", prefix, "type_is", "array", f"{prefix} é array"))
        _walk(obj[0], sample_path, depth + 1, out)


def discover_checks(response_ctx: dict) -> list[dict]:
    """Gera a lista de validacoes automaticas (source=auto) a partir de UMA
    resposta HTTP real. Retorna checks no mesmo formato aceito pelo
    avaliador (app.engine.evaluator.evaluate_check).
    """
    checks: list[dict] = []

    status_code = response_ctx.get("status_code")
    if status_code is not None:
        checks.append(
            _check("http", "$.status_code", "equals", status_code, f"HTTP status é {status_code}")
        )

    checks.append(_check("json", None, "is_valid_json", True, "Resposta é JSON válido"))

    content_type = response_ctx.get("content_type", "")
    if content_type:
        expected_ct = "application/json" if response_ctx.get("json_valid") else content_type.split(";")[0]
        checks.append(
            _check("http", "$.content_type", "contains", expected_ct, f"Content-Type contém '{expected_ct}'")
        )

    response_time = response_ctx.get("response_time_ms")
    if response_time is not None:
        # limiar generoso e AJUSTAVEL pelo usuario - nao e uma afirmacao de
        # performance ideal, apenas um ponto de partida sensato.
        threshold = max(round(response_time * 3), 2000)
        checks.append(
            _check(
                "performance",
                "$.response_time_ms",
                "less_than_or_equal",
                threshold,
                f"Tempo de resposta ≤ {threshold}ms (sugestão automática, ajustável)",
            )
        )

    if response_ctx.get("json_valid") and response_ctx.get("body_json") is not None:
        _walk(response_ctx["body_json"], "", 0, checks)

    return checks
