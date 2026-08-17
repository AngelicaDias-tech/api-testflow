"""
Importacao de massas de teste via CSV (melhoria "Massas de teste"). So
faz parsing + validacao + inferencia leve de tipo - devolve uma PREVIA
para o usuario revisar, exatamente como app/engine/curl_import.py e
app/engine/bruno_import.py ja fazem para importacao de request unica:
nada e persistido aqui, so depois de uma confirmacao explicita
(POST /requests/{id}/datasets, ver app/api/datasets.py).

Formato esperado: primeira linha = cabecalho (nomes das variaveis, viram
as chaves usadas por app.engine.templating.render_template), linhas
seguintes = um caso de teste por linha. Nao aceita cabecalho vazio/
duplicado nem linhas com numero de colunas diferente do cabecalho -
esses casos viram erros claros, nunca uma tentativa de "adivinhar".
"""

from __future__ import annotations

import csv
import io
from typing import Any


class CsvImportError(Exception):
    """Erro que impede a importacao por completo (ex: CSV vazio, sem
    cabecalho) - diferente de erros POR LINHA, que sao coletados e
    devolvidos junto com as linhas validas (ver `parse_csv`)."""


def _clean_cell(raw: str) -> str | int | float | bool:
    v = raw.strip()
    low = v.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        if v and (v.lstrip("-").isdigit()):
            return int(v)
        return float(v) if v and _looks_like_float(v) else v
    except ValueError:
        return v


def _looks_like_float(v: str) -> bool:
    try:
        float(v)
        return "." in v
    except ValueError:
        return False


def parse_csv(csv_text: str) -> dict[str, Any]:
    """Retorna {"columns": [...], "rows": [...], "errors": [...]} - `rows`
    contém só as linhas válidas (cada uma um dict coluna->valor com tipo
    inferido), `errors` descreve, com número da linha, qualquer problema
    encontrado nas demais. O chamador decide se bloqueia a importação
    (linhas com erro) ou segue só com as válidas."""
    if not csv_text or not csv_text.strip():
        raise CsvImportError("O arquivo CSV está vazio.")

    reader = csv.reader(io.StringIO(csv_text.strip()))
    rows_raw = list(reader)
    if not rows_raw:
        raise CsvImportError("O arquivo CSV está vazio.")

    header = [h.strip() for h in rows_raw[0]]
    if not header or any(not h for h in header):
        raise CsvImportError(
            "O cabeçalho do CSV precisa ter um nome de coluna em cada posição (ex: cpf,idade,valor)."
        )
    duplicated = {h for h in header if header.count(h) > 1}
    if duplicated:
        raise CsvImportError(f"O cabeçalho tem colunas repetidas: {', '.join(sorted(duplicated))}.")

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_num, raw_row in enumerate(rows_raw[1:], start=2):
        if not raw_row or all(not cell.strip() for cell in raw_row):
            continue  # linha em branco - ignorada silenciosamente, comum em CSV exportado
        if len(raw_row) != len(header):
            errors.append(
                f"Linha {line_num}: tem {len(raw_row)} coluna(s), mas o cabeçalho define {len(header)} "
                f"({', '.join(header)})."
            )
            continue
        rows.append({col: _clean_cell(val) for col, val in zip(header, raw_row, strict=True)})

    return {"columns": header, "rows": rows, "errors": errors}
