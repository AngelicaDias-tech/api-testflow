"""Exportar/Importar testes (melhoria "Exportar/Importar testes"). Cobre a
regra de seguranca inegociavel (nenhum segredo sai no arquivo) e o
round-trip estrutural (regras/cenarios/massas voltam do jeito que foram
exportados) via app/api/export_import.py, exercitado atraves da app FastAPI
completa (unico modulo do projeto que precisa disso, por mexer com
varias tabelas relacionadas)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("API_TESTFLOW_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("API_TESTFLOW_SECRET_KEY_FILE", str(tmp_path / "secret.key"))
    from app.core import config

    config.get_settings.cache_clear()
    # o engine em app.db.database ja foi criado com a config antiga na
    # importacao do modulo (import feito uma vez por processo) - recriamos
    # explicitamente para este teste usar o banco temporario isolado.
    import sqlmodel

    from app.db import database

    database.settings = config.get_settings()
    database.engine = sqlmodel.create_engine(
        database.settings.database_url, connect_args={"check_same_thread": False}
    )
    with TestClient(app) as c:
        yield c


def _create_full_project(client: TestClient) -> dict:
    project = client.post("/api/projects", json={"name": "Projeto com segredo"}).json()
    req = client.post(
        "/api/requests",
        json={
            "project_id": project["id"],
            "name": "API sensível",
            "method": "GET",
            "url": "https://api.example.com/clientes/{{cpf}}",
            "headers": {"Accept": "application/json", "Authorization": "Bearer nao-deveria-sair-daqui"},
            "auth": {"type": "bearer", "token": "token-secreto-nao-pode-vazar"},
            "body": None,
            "body_type": "none",
        },
    ).json()
    client.post(
        f"/api/requests/{req['id']}/rules",
        json={
            "source": "custom",
            "category": "field",
            "field": "status",
            "operator": "equals",
            "expected": "ACTIVE",
            "description": "status ativo",
        },
    )
    client.post(f"/api/requests/{req['id']}/scenarios", json={"name": "Cenário 1", "variables": {"cpf": "123"}})
    client.post(
        f"/api/requests/{req['id']}/datasets",
        json={"name": "massa", "columns": ["cpf"], "rows": [{"cpf": "111"}, {"cpf": "222"}]},
    )
    return project


def test_export_nunca_inclui_token_nem_header_sensivel(client: TestClient):
    project = _create_full_project(client)
    bundle = client.get(f"/api/projects/{project['id']}/export").json()

    bundle_text = str(bundle)
    assert "token-secreto-nao-pode-vazar" not in bundle_text
    assert "nao-deveria-sair-daqui" not in bundle_text
    assert "Authorization" not in bundle["requests"][0]["headers"]
    assert bundle["requests"][0]["headers"] == {"Accept": "application/json"}
    assert bundle["requests"][0]["auth"] == {
        "type": "bearer",
        "key_name": None,
        "location": None,
        "username": None,
    }


def test_export_inclui_versao_e_estrutura_completa(client: TestClient):
    project = _create_full_project(client)
    bundle = client.get(f"/api/projects/{project['id']}/export").json()

    assert bundle["testflow_export_version"] == "1.0"
    exp_req = bundle["requests"][0]
    assert len(exp_req["rules"]) == 1
    assert len(exp_req["scenarios"]) == 1
    assert len(exp_req["datasets"]) == 1
    assert exp_req["datasets"][0]["rows"] == [{"cpf": "111"}, {"cpf": "222"}]


def test_import_cria_projeto_novo_com_tudo_exceto_segredo(client: TestClient):
    project = _create_full_project(client)
    bundle = client.get(f"/api/projects/{project['id']}/export").json()

    resp = client.post("/api/projects/import", json=bundle)
    assert resp.status_code == 201
    summary = resp.json()

    assert summary["project"]["id"] != project["id"]  # projeto NOVO, nunca sobrescreve
    assert summary["requests_imported"] == 1
    assert summary["rules_imported"] == 1
    assert summary["scenarios_imported"] == 1
    assert summary["datasets_imported"] == 1
    assert summary["requests_needing_auth"] == ["API sensível"]

    new_reqs = client.get(f"/api/requests?project_id={summary['project']['id']}").json()
    assert len(new_reqs) == 1
    # auth restaurada so com o TIPO, sem o token
    assert new_reqs[0]["auth"] == {"type": "bearer"}

    new_rules = client.get(f"/api/requests/{new_reqs[0]['id']}/rules").json()
    assert len(new_rules) == 1
    assert new_rules[0]["expected"] == "ACTIVE"


def test_import_rejeita_versao_nao_suportada(client: TestClient):
    bundle = {
        "testflow_export_version": "99.0",
        "project": {"name": "x", "description": None},
        "requests": [],
    }
    resp = client.post("/api/projects/import", json=bundle)
    assert resp.status_code == 400
    assert "vers" in resp.json()["detail"].lower()


def test_import_com_estrutura_invalida_da_erro_amigavel_422(client: TestClient):
    resp = client.post("/api/projects/import", json={"testflow_export_version": "1.0"})  # falta 'project'
    assert resp.status_code == 422
    assert "project" in resp.json()["detail"]


def test_export_de_projeto_inexistente_e_404(client: TestClient):
    resp = client.get("/api/projects/nao-existe/export")
    assert resp.status_code == 404
