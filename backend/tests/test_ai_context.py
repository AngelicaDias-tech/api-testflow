"""Montagem/mascaramento de contexto para a IA (melhoria "Integração
contextual da IA") - app/ai/context.py."""

from __future__ import annotations

from app.ai.context import build_chat_context, mask_response_ctx


def test_mask_response_ctx_mascara_headers_sensiveis():
    ctx = mask_response_ctx({"status_code": 200, "headers": {"Authorization": "Bearer abc123secreto"}})
    assert "abc123secreto" not in str(ctx)
    assert ctx["status_code"] == 200


def test_mask_response_ctx_none_permanece_none():
    assert mask_response_ctx(None) is None
    assert mask_response_ctx({}) == {}


def test_mask_response_ctx_nao_mascara_headers_nao_sensiveis():
    ctx = mask_response_ctx({"headers": {"Content-Type": "application/json"}})
    assert ctx["headers"]["Content-Type"] == "application/json"


def test_build_chat_context_so_inclui_o_que_foi_fornecido():
    ctx = build_chat_context(method="GET", url="https://x.com")
    assert ctx == {"method": "GET", "url": "https://x.com"}


def test_build_chat_context_mascara_headers_do_response_ctx():
    ctx = build_chat_context(
        method="GET",
        url="https://x.com",
        response_ctx={"status_code": 401, "headers": {"Authorization": "Bearer segredo-real"}},
    )
    assert "segredo-real" not in str(ctx)
    assert ctx["status_code"] == 401


def test_build_chat_context_reduz_rules_aos_campos_essenciais():
    ctx = build_chat_context(
        rules=[
            {
                "id": "rule-1",
                "field": "status",
                "operator": "equals",
                "expected": "ACTIVE",
                "created_at": "2026-01-01",
            }
        ]
    )
    assert ctx["rules"] == [{"field": "status", "operator": "equals", "expected": "ACTIVE"}]
    assert "id" not in ctx["rules"][0]
    assert "created_at" not in ctx["rules"][0]


def test_build_chat_context_inclui_execution_result_quando_fornecido():
    result = {"field": "status", "operator": "equals", "expected": "ACTIVE", "actual": "INACTIVE"}
    ctx = build_chat_context(execution_result=result)
    assert ctx["execution_result"] == result


def test_build_chat_context_nunca_vaza_body_json_bruto_sem_pedir():
    # body_json so entra se vier dentro de response_ctx explicitamente —
    # nunca e inventado/preenchido por conta propria.
    ctx = build_chat_context(method="GET", url="https://x.com")
    assert "body_json" not in ctx
