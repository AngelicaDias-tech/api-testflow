"""
Orquestracao da execucao real de pytest (secao 15/16 do spec).

Fluxo: monta um "spec" (requisicao + checks) -> grava em arquivo JSON em
um diretorio temporario -> roda `python -m pytest` como subprocesso
(mesmo interpretador do backend, via sys.executable) usando
pytest-json-report -> le o relatorio JSON (autoridade de PASS/FAIL) e o
arquivo auxiliar de actual/expected -> devolve uma lista de resultados
prontos para persistir e exibir no dashboard.

Rodar como subprocesso (em vez de chamar pytest.main() in-process) isola
cada execucao (evita estado global do pytest vazar entre execucoes
concorrentes de squads diferentes) e reflete fielmente "o pytest decide".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from app.core.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = BACKEND_ROOT / "app" / "engine" / "pytest_project" / "test_rules.py"


class PytestRunError(RuntimeError):
    pass


def run_pytest(request_def: dict, checks: list[dict]) -> dict:
    """Executa os checks fornecidos contra a requisicao e retorna:
    {"summary": {...}, "results": [...], "raw_report": {...}}
    """
    settings = get_settings()
    run_id = str(uuid.uuid4())

    with tempfile.TemporaryDirectory(prefix=f"api_testflow_run_{run_id}_") as tmp:
        tmp_path = Path(tmp)
        spec_file = tmp_path / "spec.json"
        results_file = tmp_path / "results.jsonl"
        report_file = tmp_path / "report.json"

        spec = {
            "request": request_def,
            "checks": checks,
            "timeout": settings.http_timeout_seconds,
        }
        spec_file.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        results_file.touch()

        env = {
            **os.environ,
            "API_TESTFLOW_SPEC_FILE": str(spec_file),
            "API_TESTFLOW_RESULTS_FILE": str(results_file),
        }

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(TEST_FILE),
            "--json-report",
            f"--json-report-file={report_file}",
            "-p",
            "no:cacheprovider",
            "-q",
        ]

        proc = subprocess.run(
            cmd,
            cwd=str(BACKEND_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=settings.http_timeout_seconds + 60,
        )

        if not report_file.exists():
            raise PytestRunError(
                f"pytest nao gerou relatorio. stdout={proc.stdout[-2000:]} stderr={proc.stderr[-2000:]}"
            )

        raw_report = json.loads(report_file.read_text(encoding="utf-8"))
        actual_expected_by_id = _read_results_jsonl(results_file)

    checks_by_id = {c["id"]: c for c in checks}
    results = []
    for test in raw_report.get("tests", []):
        check_id = _extract_check_id(test["nodeid"])
        check = checks_by_id.get(check_id, {})
        extra = actual_expected_by_id.get(check_id, {})
        results.append(
            {
                "rule_id": check_id,
                "node_id": test["nodeid"],
                "name": check.get("description") or check.get("field") or check.get("category") or check_id,
                "category": check.get("category"),
                "field": check.get("field"),
                "operator": check.get("operator"),
                "expected": _stringify(extra.get("expected", check.get("expected"))),
                "actual": _stringify(extra.get("actual")),
                "outcome": test["outcome"],
                "message": extra.get("message") or test.get("call", {}).get("longrepr"),
                "duration_ms": round(test.get("call", {}).get("duration", test.get("duration", 0)) * 1000, 2),
                "source": check.get("source"),
            }
        )

    summary = raw_report.get("summary", {})
    return {
        "summary": {
            "total": summary.get("total", len(results)),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "skipped": summary.get("skipped", 0),
            "error": summary.get("error", 0),
            "duration_ms": round(raw_report.get("duration", 0) * 1000, 2),
        },
        "results": results,
        "stdout": proc.stdout,
    }


def _extract_check_id(node_id: str) -> str:
    if "[" in node_id and node_id.endswith("]"):
        return node_id[node_id.index("[") + 1 : -1]
    return node_id


def _read_results_jsonl(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        out[row["id"]] = row
    return out


def _stringify(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


