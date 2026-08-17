"""_collect_known_variables (melhoria "IA para massas") - decide quais
colunas a IA pode gerar para uma massa. Cobre o caso com placeholders
`{{var}}` (já existente) e o caso sem nenhum placeholder, só um body JSON
com valores literais (ex: POST https://dummyjson.com/products/add) -
sem esse fallback, uma API sem `{{var}}` nunca teria massa gerada por IA."""

from __future__ import annotations

from app.api.ai import _collect_known_variables
from app.db.models import ApiRequestDef


def _req(**kwargs) -> ApiRequestDef:
    base = {
        "project_id": "p1",
        "name": "req",
        "method": "POST",
        "url": "https://api.example.com",
        "headers": {},
        "query_params": {},
        "body": None,
        "body_type": "none",
        "auth": {"type": "none"},
    }
    base.update(kwargs)
    return ApiRequestDef(**base)


def test_usa_placeholders_quando_existem():
    req = _req(url="https://api.example.com/clientes/{{cpf}}")
    assert _collect_known_variables(req, []) == ["cpf"]


def test_cai_para_chaves_do_body_json_sem_placeholder():
    req = _req(body='{"title": "Notebook", "price": 3500, "stock": 10, "category": "electronics"}')
    assert _collect_known_variables(req, []) == ["title", "price", "stock", "category"]


def test_placeholder_tem_prioridade_sobre_body_json():
    req = _req(url="https://api.example.com/{{id}}", body='{"title": "Notebook"}')
    assert _collect_known_variables(req, []) == ["id"]


def test_body_nao_json_nao_gera_variavel_inventada():
    req = _req(body="isto nao e json")
    assert _collect_known_variables(req, []) == []


def test_sem_body_e_sem_placeholder_retorna_vazio():
    assert _collect_known_variables(_req(), []) == []
