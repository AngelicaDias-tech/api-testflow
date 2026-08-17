"""Request efetivamente enviado, para exibicao na UI (melhoria 2). Cobre
sobretudo o ponto de seguranca que motivou nao alterar a assinatura de
build_httpx_request_kwargs: uma auth "custom" usa um NOME de header livre,
que pode nao bater com a lista fixa de nomes sensiveis conhecidos
(app.core.security._SENSITIVE_HEADER_NAMES) - build_sent_snapshot precisa
mascarar mesmo assim."""

from __future__ import annotations

from app.core.security import encrypt_auth_for_storage, encrypt_headers_for_storage
from app.engine.http_executor import build_sent_snapshot


def _req(auth: dict, headers: dict | None = None, method="GET", body=None, body_type="none") -> dict:
    return {
        "method": method,
        "url": "https://api.example.com/clientes/123?ativo=true",
        "headers": encrypt_headers_for_storage(headers or {}),
        "query_params": {},
        "body": body,
        "body_type": body_type,
        "auth": encrypt_auth_for_storage(auth),
    }


def test_get_sem_body_nao_inventa_body():
    snap = build_sent_snapshot(_req({"type": "none"}))
    assert snap["method"] == "GET"
    assert snap["body"] is None
    assert snap["body_type"] == "none"
    assert snap["query_params"] == {"ativo": "true"}


def test_post_com_body_mostra_body_real():
    snap = build_sent_snapshot(
        _req({"type": "none"}, method="POST", body='{"cpf": "123"}', body_type="json")
    )
    assert snap["method"] == "POST"
    assert snap["body"] == '{"cpf": "123"}'


def test_bearer_mascarado_no_snapshot():
    snap = build_sent_snapshot(_req({"type": "bearer", "token": "super-secret-token"}))
    assert "super-secret-token" not in str(snap)
    assert "*" in snap["headers"]["Authorization"]


def test_auth_custom_com_header_fora_da_lista_conhecida_e_mascarada():
    # "X-Minha-Auth-Especial" nao esta em _SENSITIVE_HEADER_NAMES - o
    # mascaramento generico por nome NAO cobriria isso sozinho.
    snap = build_sent_snapshot(
        _req({"type": "custom", "key_name": "X-Minha-Auth-Especial", "api_key": "valor-secreto-123"})
    )
    assert "valor-secreto-123" not in str(snap)
    assert "X-Minha-Auth-Especial" in snap["headers"]


def test_api_key_em_query_e_mascarada():
    snap = build_sent_snapshot(
        _req({"type": "api_key", "key_name": "api_key", "api_key": "chave-secreta", "location": "query"})
    )
    assert "chave-secreta" not in str(snap)
    assert snap["query_params"]["api_key"] != "chave-secreta"


def test_basic_auth_mostra_placeholder_sem_credenciais():
    snap = build_sent_snapshot(_req({"type": "basic", "username": "user", "password": "senha-real"}))
    assert "senha-real" not in str(snap)
    assert snap["headers"]["Authorization"] == "Basic ********"


def test_headers_nao_sensiveis_do_usuario_continuam_visiveis():
    snap = build_sent_snapshot(_req({"type": "none"}, headers={"Accept": "application/json"}))
    assert snap["headers"]["Accept"] == "application/json"
