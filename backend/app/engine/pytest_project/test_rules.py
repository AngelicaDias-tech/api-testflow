"""
O UNICO modulo de teste real da plataforma. Um teste (`test_check`) por
check, parametrizado dinamicamente pelo conftest a partir do spec da
execucao. Isso e literalmente o pytest fazendo a validacao - o assert
abaixo e o que decide PASS/FAIL, nao o backend.
"""

from __future__ import annotations

import json
import os

import pytest

from app.engine.evaluator import evaluate_check


def _record_actual_expected(check: dict, result) -> None:
    """Grava o par observado/esperado para TODO check (passou ou falhou).

    O relatorio nativo do pytest so traz detalhes ricos em caso de falha
    (via a mensagem do assert). Para exibir "Actual" tambem nos testes que
    passaram (secao 17), gravamos um arquivo auxiliar aqui - pytest ainda
    decide PASS/FAIL sozinho, isto so enriquece a apresentacao.
    """
    results_file = os.environ.get("API_TESTFLOW_RESULTS_FILE")
    if not results_file:
        return
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "id": check["id"],
                    "actual": result.actual,
                    "expected": result.expected,
                    "passed": result.passed,
                    "message": result.message,
                },
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


def test_check(response_ctx: dict, check: dict) -> None:
    result = evaluate_check(check, response_ctx)
    _record_actual_expected(check, result)
    if result.skipped:
        # Regra condicional cuja condicao nao foi satisfeita: NAO e PASS
        # nem FAIL, pytest.skip() e quem decide - o proprio pytest reporta
        # "skipped" (nao um mecanismo paralelo do backend).
        pytest.skip(result.message)
    assert result.passed, (
        f"{check.get('description') or check.get('field') or check.get('category')}: "
        f"esperado={result.expected!r} observado={result.actual!r} ({result.message})"
    )
