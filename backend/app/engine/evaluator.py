"""
Motor de avaliacao de uma unica regra/check contra o contexto de uma
resposta HTTP ja capturada.

Por que existe separado: esta funcao e usada em DOIS lugares -
(1) pelo backend, para pre-visualizar "observado" antes de qualquer teste
    rodar (secao 9), e
(2) pelos testes pytest gerados dinamicamente (app/engine/pytest_project),
    que sao executados em um subprocesso separado.
Compartilhar o mesmo modulo garante que "o que o dashboard mostra" e
"o que o pytest realmente verificou" nunca divirjam - pytest continua
sendo a unica autoridade de PASS/FAIL (secao 15), este modulo so define
a REGRA da comparacao, nao decide se o teste "conta" como passou no
relatorio final (isso e sempre o assert do pytest).

Regras condicionais/sobre listas (ex: "clientes PREMIUM devem estar
ativos"): um check pode opcionalmente trazer `array_path` +
`condition_field`/`condition_operator`/`condition_expected`. Quando
presentes, a regra e aplicada a CADA elemento do array em `array_path`
que satisfizer a condicao - e generico para qualquer API com uma lista
de objetos na resposta (nao e um mecanismo especifico de nenhum cliente).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

MISSING = object()


@dataclass
class EvalResult:
    passed: bool
    actual: Any
    expected: Any
    message: str
    # True quando a regra e CONDICIONAL e a condicao nao foi satisfeita por
    # nenhum item (ou pelo unico objeto, no caso de resposta plana) - nesse
    # caso a regra dependente nao deve ser avaliada como PASS nem FAIL, e
    # sim reportada como SKIPPED pelo proprio pytest (ver
    # pytest_project/test_rules.py). `passed` fica True so por seguranca de
    # quem inspecionar o dataclass diretamente sem checar `skipped` antes.
    skipped: bool = False


def get_by_path(obj: Any, path: str) -> Any:
    """Resolve um dot-path simples, incluindo indices numericos de array.

    Exemplos: "id", "data.status", "items.0.name"
    """
    if path in ("", None):
        return obj
    current = obj
    for part in path.split("."):
        if current is MISSING or current is None:
            return MISSING
        if isinstance(current, list):
            if not part.lstrip("-").isdigit():
                return MISSING
            idx = int(part)
            if idx < 0 or idx >= len(current):
                return MISSING
            current = current[idx]
        elif isinstance(current, dict):
            if part not in current:
                return MISSING
            current = current[part]
        else:
            return MISSING
    return current


def _resolve_actual(field: str | None, ctx: dict) -> Any:
    if field is None or field == "":
        return MISSING
    if field == "$.status_code":
        return ctx["status_code"]
    if field == "$.content_type":
        return ctx.get("content_type")
    if field == "$.response_time_ms":
        return ctx.get("response_time_ms")
    if field == "$.json_valid":
        return ctx.get("json_valid")
    body = ctx.get("body_json")
    if body is None and not ctx.get("json_valid"):
        return MISSING
    return get_by_path(body, field)


def type_name(value: Any) -> str:
    if value is MISSING:
        return "missing"
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
    return type(value).__name__


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def evaluate_check(check: dict, ctx: dict) -> EvalResult:
    """Avalia um check/regra contra o contexto da resposta.

    check: {"field": str|None, "operator": str, "expected": Any,
            "array_path": str|None, "condition_field"/"condition_operator"/
            "condition_expected": opcionais, ...}
    ctx: contexto da resposta (status_code, headers, content_type, body_json,
         json_valid, response_time_ms)
    """
    operator = check["operator"]

    if operator == "is_valid_json":
        passed = bool(ctx.get("json_valid"))
        return EvalResult(passed, ctx.get("json_valid"), True, "JSON valido")

    array_path = check.get("array_path")
    if array_path is not None:
        return _evaluate_array_check(check, ctx, array_path)

    field = check.get("field")
    expected = check.get("expected")
    actual = _resolve_actual(field, ctx)
    return _evaluate_resolved(operator, field, actual, expected)


def _evaluate_array_check(check: dict, ctx: dict, array_path: str) -> EvalResult:
    """Aplica field/operator/expected a cada elemento de um array que
    satisfizer condition_field/condition_operator/condition_expected.

    Semantica: "para todo item que satisfaz a condicao, o campo deve
    satisfazer a regra" - se nenhum item satisfizer a condicao, a regra e
    considerada vacuamente satisfeita (mas isso fica visivel na mensagem,
    para nao esconder silenciosamente um cenario "0 itens testados").

    Tambem cobre regras condicionais sobre uma resposta PLANA (sem lista) -
    ex: "Se o repositorio for publico, garanta mais de 100 estrelas" contra
    um unico objeto JSON: se `array_path` resolver para um dict (nao uma
    lista), ele e tratado como uma lista de um item so, reaproveitando
    exatamente a mesma logica de condicao+regra abaixo em vez de duplicar um
    mecanismo separado so para o caso "sem array".
    """
    body = ctx.get("body_json")
    items = get_by_path(body, array_path) if array_path != "" else body
    if isinstance(items, dict):
        items = [items]
    if items is MISSING or not isinstance(items, list):
        return EvalResult(
            False,
            "<lista ausente>",
            check.get("expected"),
            f"'{array_path or '(raiz)'}' nao e uma lista na resposta observada",
        )

    condition_field = check.get("condition_field")
    condition_operator = check.get("condition_operator") or "equals"
    condition_expected = check.get("condition_expected")

    matched_indices: list[int] = []
    for idx, item in enumerate(items):
        if condition_field:
            cond_actual = get_by_path(item, condition_field)
            cond_result = _evaluate_resolved(condition_operator, condition_field, cond_actual, condition_expected)
            if not cond_result.passed:
                continue
        matched_indices.append(idx)

    total = len(items)
    label = f"{condition_field} {condition_operator} {condition_expected!r}" if condition_field else "(sem filtro)"

    if not matched_indices:
        return EvalResult(
            True,
            f"0/{total} itens correspondem à condição",
            f"todos: {check.get('field')} {check.get('operator')} {check.get('expected')}",
            f"Condição ({label}) não satisfeita — regra dependente não avaliada (SKIPPED).",
            skipped=True,
        )

    field = check["field"]
    operator = check["operator"]
    expected = check.get("expected")
    failures: list[tuple[int, Any]] = []
    for idx in matched_indices:
        item_actual = get_by_path(items[idx], field)
        result = _evaluate_resolved(operator, field, item_actual, expected)
        if not result.passed:
            failures.append((idx, result.actual))

    passed = len(failures) == 0
    ok_count = len(matched_indices) - len(failures)
    actual_summary = f"{ok_count}/{len(matched_indices)} itens OK"
    if failures:
        preview = "; ".join(f"item[{i}]={a!r}" for i, a in failures[:5])
        actual_summary += f" — falhas: {preview}" + (" ..." if len(failures) > 5 else "")

    message = (
        f"{len(matched_indices)}/{total} itens correspondem a {label}; "
        f"verificando {field} {operator} {expected!r} em cada um"
    )
    return EvalResult(passed, actual_summary, f"todos: {field} {operator} {expected}", message)


def _evaluate_resolved(operator: str, field: str | None, actual: Any, expected: Any) -> EvalResult:
    """Aplica UM operador a um valor `actual` ja resolvido. Reaproveitado
    tanto para checks simples (campo direto da resposta) quanto para cada
    item de uma regra condicional sobre array, e para a propria condicao
    de filtro (condition_field/condition_operator/condition_expected)."""
    if operator == "exists":
        passed = actual is not MISSING
        return EvalResult(passed, _display(actual), "campo presente", _msg(field, "exists"))
    if operator == "not_exists":
        passed = actual is MISSING
        return EvalResult(passed, _display(actual), "campo ausente", _msg(field, "not_exists"))

    if actual is MISSING and operator not in ("type_is",):
        return EvalResult(False, "<ausente>", expected, f"Campo '{field}' nao encontrado na resposta")

    if operator == "type_is":
        actual_type = type_name(actual)
        passed = actual_type == str(expected)
        return EvalResult(passed, actual_type, expected, _msg(field, "type_is"))

    if operator == "equals":
        passed = str(actual) == str(expected) if not isinstance(actual, bool) else actual == _coerce_bool(expected)
        return EvalResult(passed, actual, expected, _msg(field, "equals"))

    if operator == "not_equals":
        passed = str(actual) != str(expected)
        return EvalResult(passed, actual, expected, _msg(field, "not_equals"))

    if operator == "contains":
        passed = str(expected) in str(actual) if not isinstance(actual, list) else expected in actual
        return EvalResult(passed, actual, expected, _msg(field, "contains"))

    if operator == "not_contains":
        passed = str(expected) not in str(actual) if not isinstance(actual, list) else expected not in actual
        return EvalResult(passed, actual, expected, _msg(field, "not_contains"))

    if operator == "starts_with":
        passed = str(actual).startswith(str(expected))
        return EvalResult(passed, actual, expected, _msg(field, "starts_with"))

    if operator == "ends_with":
        passed = str(actual).endswith(str(expected))
        return EvalResult(passed, actual, expected, _msg(field, "ends_with"))

    if operator in ("greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal"):
        try:
            a, e = float(actual), float(expected)
        except (TypeError, ValueError):
            return EvalResult(False, actual, expected, f"Campo '{field}' nao e numerico")
        passed = {
            "greater_than": a > e,
            "greater_than_or_equal": a >= e,
            "less_than": a < e,
            "less_than_or_equal": a <= e,
        }[operator]
        return EvalResult(passed, actual, expected, _msg(field, operator))

    if operator == "matches_regex":
        try:
            passed = re.search(str(expected), str(actual)) is not None
        except re.error:
            passed = False
        return EvalResult(passed, actual, expected, _msg(field, "matches_regex"))

    if operator == "is_email_format":
        passed = bool(_EMAIL_RE.match(str(actual)))
        return EvalResult(passed, actual, "formato de email valido", _msg(field, "is_email_format"))

    raise ValueError(f"Operador desconhecido: {operator}")


def _coerce_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def _display(v: Any) -> Any:
    return None if v is MISSING else v


def _msg(field: str | None, operator: str) -> str:
    return f"{field or '(global)'} {operator}"
