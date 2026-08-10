"""
Este conftest e o coracao da ponte "UI -> pytest" (secao 15 do spec).

Nenhum dado do usuario (URL, regras, valores esperados) e transformado em
CODIGO PYTHON gerado dinamicamente - isso seria um risco serio de injecao
de codigo, ja que o conteudo vem de squads diferentes testando APIs
arbitrarias. Em vez disso:

  1. o backend escreve um arquivo JSON ("spec") com a requisicao e a lista
     de checks a validar;
  2. este conftest le esse JSON (via variavel de ambiente
     API_TESTFLOW_SPEC_FILE) e usa `pytest_generate_tests` para
     parametrizar UM teste pytest de verdade por check;
  3. a requisicao HTTP real e feita UMA vez (fixture de sessao) e
     reaproveitada por todos os checks daquela execucao.

O modulo de teste em si (test_rules.py) nunca contem dados do usuario -
apenas logica fixa que LE dados de fora. pytest continua sendo quem decide
PASS/FAIL: o backend so consome o relatorio que o pytest produz.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.engine.http_executor import execute_request  # noqa: E402


def _load_spec() -> dict:
    spec_path = os.environ["API_TESTFLOW_SPEC_FILE"]
    with open(spec_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def spec() -> dict:
    return _load_spec()


@pytest.fixture(scope="session")
def response_ctx(spec: dict) -> dict:
    return execute_request(spec["request"], timeout=spec.get("timeout", 15))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "check" in metafunc.fixturenames:
        spec = _load_spec()
        checks = spec["checks"]
        metafunc.parametrize("check", checks, ids=[c["id"] for c in checks])
