"""
Autenticacao por token nas chamadas HTTP reais (secao "Autenticacao" do
pedido). Cobre exatamente os 5 testes obrigatorios: sem token, Bearer,
API Key, header personalizado, e token invalido (erro normal, sem
vazamento). Todos exercitam `build_httpx_request_kwargs`/`execute_request`
em app/engine/http_executor.py - o MESMO ponto usado tanto pelo "Testar
API" (probe) quanto pela execucao real via pytest (conftest.py importa
`execute_request` diretamente) - entao nao ha um caminho HTTP paralelo.
"""

from __future__ import annotations

import httpx

from app.core.security import decrypt_value, encrypt_auth_for_storage, mask_auth
from app.engine.http_executor import build_httpx_request_kwargs, execute_request


def _base_request_def(auth: dict, headers: dict | None = None) -> dict:
    return {
        "method": "GET",
        "url": "https://api.example.com/data",
        "headers": headers or {},
        "query_params": {},
        "body": None,
        "body_type": "none",
        "auth": auth,
    }


# ---------------------------------------------------------------------
# TESTE 1 - API sem token: continua funcionando exatamente como antes.
# ---------------------------------------------------------------------
def test_sem_autenticacao_nenhum_header_extra_e_enviado():
    req = _base_request_def({"type": "none"})
    kwargs = build_httpx_request_kwargs(req)
    assert "Authorization" not in kwargs["headers"]
    assert kwargs["headers"] == {}
    assert "auth" not in kwargs


def test_sem_autenticacao_headers_manuais_do_usuario_continuam_intactos():
    # Fluxo atual (headers avulsos, sem nenhuma auth) nao pode ser afetado.
    req = _base_request_def({"type": "none"}, headers={"Accept": "application/json"})
    kwargs = build_httpx_request_kwargs(req)
    assert kwargs["headers"] == {"Accept": "application/json"}


# ---------------------------------------------------------------------
# TESTE 2 - Bearer Token: Authorization: Bearer <token> enviado corretamente.
# ---------------------------------------------------------------------
def test_bearer_token_envia_header_authorization_correto():
    req = _base_request_def({"type": "bearer", "token": "eyJhbGciOiJIUzI1NiIs"})
    kwargs = build_httpx_request_kwargs(req)
    assert kwargs["headers"]["Authorization"] == "Bearer eyJhbGciOiJIUzI1NiIs"


def test_bearer_token_nunca_vai_para_query_params():
    req = _base_request_def({"type": "bearer", "token": "secret-token"})
    kwargs = build_httpx_request_kwargs(req)
    assert "secret-token" not in str(kwargs.get("params", {}))


# ---------------------------------------------------------------------
# TESTE 3 - API Key: header configuravel enviado corretamente.
# ---------------------------------------------------------------------
def test_api_key_com_nome_de_header_customizado():
    req = _base_request_def({"type": "api_key", "key_name": "X-API-Key", "api_key": "abc123"})
    kwargs = build_httpx_request_kwargs(req)
    assert kwargs["headers"]["X-API-Key"] == "abc123"


def test_api_key_funciona_com_qualquer_nome_de_header():
    req = _base_request_def({"type": "api_key", "key_name": "api-key", "api_key": "abc123"})
    kwargs = build_httpx_request_kwargs(req)
    assert kwargs["headers"]["api-key"] == "abc123"


def test_api_key_pode_ir_para_query_quando_configurado():
    req = _base_request_def(
        {"type": "api_key", "key_name": "api_key", "api_key": "abc123", "location": "query"}
    )
    kwargs = build_httpx_request_kwargs(req)
    assert kwargs["params"]["api_key"] == "abc123"
    assert "api_key" not in kwargs["headers"]


# ---------------------------------------------------------------------
# TESTE 4 - Header personalizado: nome e valor informados pelo usuario.
# ---------------------------------------------------------------------
def test_auth_personalizada_envia_header_exato_informado_pelo_usuario():
    req = _base_request_def({"type": "custom", "key_name": "X-Access-Token", "api_key": "abc123"})
    kwargs = build_httpx_request_kwargs(req)
    assert kwargs["headers"]["X-Access-Token"] == "abc123"


def test_auth_personalizada_sem_nome_de_header_nao_adiciona_nada():
    req = _base_request_def({"type": "custom", "key_name": "", "api_key": "abc123"})
    kwargs = build_httpx_request_kwargs(req)
    assert kwargs["headers"] == {}


def test_auth_personalizada_convive_com_headers_adicionais_do_usuario():
    # Requisito 6: headers adicionais (editor de Headers, ja existente)
    # continuam sendo enviados junto com a autenticacao.
    req = _base_request_def(
        {"type": "custom", "key_name": "X-Access-Token", "api_key": "abc123"},
        headers={"Accept": "application/json", "X-Custom-Header": "abc123"},
    )
    kwargs = build_httpx_request_kwargs(req)
    assert kwargs["headers"]["Accept"] == "application/json"
    assert kwargs["headers"]["X-Custom-Header"] == "abc123"
    assert kwargs["headers"]["X-Access-Token"] == "abc123"


# ---------------------------------------------------------------------
# TESTE 5 - Token invalido: a API responde com erro normalmente, o
# TestFlow nao quebra, e o token nunca aparece na resposta/erro.
# ---------------------------------------------------------------------
def test_token_invalido_api_responde_401_sem_quebrar_a_aplicacao():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(401, json={"detail": "Invalid token"})

    transport = httpx.MockTransport(handler)
    req = _base_request_def({"type": "bearer", "token": "token-invalido-de-teste"})

    ctx = execute_request(req, timeout=5, transport=transport)

    # nao quebra a aplicacao: nao levanta excecao, retorna um contexto normal
    assert ctx["error"] is None
    assert ctx["status_code"] == 401
    assert ctx["json_valid"] is True
    assert ctx["body_json"] == {"detail": "Invalid token"}
    # o header foi de fato enviado (prova que a autenticacao realmente rodou)
    assert captured["authorization"] == "Bearer token-invalido-de-teste"
    # o token nunca aparece na mensagem de erro (aqui nao ha erro nenhum)
    assert "token-invalido-de-teste" not in str(ctx.get("error"))


def test_token_invalido_por_falha_de_conexao_tambem_nao_expoe_o_token():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(handler)
    req = _base_request_def({"type": "bearer", "token": "token-super-secreto"})

    ctx = execute_request(req, timeout=5, transport=transport)

    assert ctx["error"] is not None
    assert "token-super-secreto" not in ctx["error"]


# ---------------------------------------------------------------------
# Requisito 7 - seguranca: nunca em texto puro no armazenamento/mascarado
# na interface. Cobre o tipo "custom" especificamente (reaproveita os
# mesmos campos key_name/api_key do tipo "api_key", que ja sao
# criptografados/mascarados por nome de campo em security.py).
# ---------------------------------------------------------------------
def test_auth_personalizada_e_criptografada_para_armazenamento():
    stored = encrypt_auth_for_storage({"type": "custom", "key_name": "X-Access-Token", "api_key": "abc123"})
    assert stored["api_key"] != "abc123"
    assert decrypt_value(stored["api_key"]) == "abc123"


def test_auth_personalizada_e_mascarada_para_a_interface():
    masked = mask_auth({"type": "custom", "key_name": "X-Access-Token", "api_key": "abc123456789"})
    assert masked["api_key"] != "abc123456789"
    assert "abc123456789" not in masked["api_key"]
