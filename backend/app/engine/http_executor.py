"""
Executor HTTP real (httpx). Responsavel por transformar uma definicao de
requisicao (metodo/url/headers/params/body/auth) em uma chamada HTTP de
verdade e capturar tudo que a secao 7 do spec pede: status, headers, body,
JSON, tempo de resposta.

Por que httpx: cliente HTTP moderno, sincrono e assincrono, mantido e
gratuito, usado tanto pelo backend quanto pelos testes pytest gerados.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx

from app.core.security import decrypt_headers_for_request, decrypt_value


def split_url_query(url: str) -> tuple[str, dict[str, str]]:
    """Separa uma URL em (base sem query string, dict de query params).

    Por que isso existe: httpx.Client.request(url, params=...) NAO faz merge
    de `params` com a query string ja presente na `url` - ele SUBSTITUI a
    query inteira, mesmo que `params` seja um dict vazio. Como o usuario
    pode simplesmente colar uma URL completa (com `?...`) no campo URL sem
    nunca preencher o editor de query params, isso apagava silenciosamente
    todos os parametros da requisicao real (bug real observado com a API
    Open-Meteo: a chamada saia sem `latitude`/`longitude`/`current_weather`,
    a API respondia 200 com um corpo minimo, e a UI mostrava "nao e JSON").

    A correcao e sempre extrair a query da URL e fazer o merge explicitamente
    ANTES de chamar o httpx, para qualquer API - nao apenas para quem colou a
    URL inteira, mas tambem preservando o comportamento de quem ja usa o
    editor de query params (URL vem limpa do import de cURL/Bruno).
    """
    parts = urlsplit(url)
    query_from_url = dict(parse_qsl(parts.query, keep_blank_values=True))
    base_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment))
    return base_url, query_from_url


def build_httpx_request_kwargs(request_def: dict) -> dict:
    """Monta headers/auth/params/body prontos para o httpx a partir da
    definicao de requisicao armazenada (com segredos ainda criptografados).
    """
    headers = decrypt_headers_for_request(dict(request_def.get("headers") or {}))
    params = dict(request_def.get("query_params") or {})
    auth = request_def.get("auth") or {}
    auth_type = auth.get("type", "none")

    if auth_type == "bearer":
        token = decrypt_value(auth.get("token", ""))
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key":
        key_name = auth.get("key_name", "X-API-Key")
        key_value = decrypt_value(auth.get("api_key", ""))
        location = auth.get("location", "header")
        if location == "query":
            params[key_name] = key_value
        else:
            headers[key_name] = key_value
    elif auth_type == "custom":
        # Header personalizado: nome e valor livres, sempre enviado como
        # header (nunca na URL/query) - reaproveita os MESMOS campos
        # key_name/api_key do tipo "api_key" (mesmo formato, sem o seletor
        # de local), entao a criptografia/mascaramento em security.py ja
        # cobre isso automaticamente sem nenhuma mudanca (a chave "api_key"
        # ja esta em _SENSITIVE_AUTH_FIELDS).
        key_name = auth.get("key_name", "")
        key_value = decrypt_value(auth.get("api_key", ""))
        if key_name:
            headers[key_name] = key_value
    elif auth_type == "basic":
        # httpx cuida do Basic Auth encoding; passamos via kwarg 'auth' abaixo.
        pass

    kwargs: dict[str, Any] = {"headers": headers, "params": params}

    if auth_type == "basic":
        username = auth.get("username", "")
        password = decrypt_value(auth.get("password", ""))
        kwargs["auth"] = (username, password)

    body_type = request_def.get("body_type", "none")
    body = request_def.get("body")
    if body and body_type == "json":
        kwargs["content"] = body.encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    elif body and body_type == "text":
        kwargs["content"] = body.encode("utf-8")

    return kwargs


def execute_request(
    request_def: dict, timeout: float = 15.0, transport: httpx.BaseTransport | None = None
) -> dict:
    """Executa a requisicao e retorna um contexto de resposta normalizado,
    usado tanto pela descoberta automatica quanto pelo avaliador de regras.

    `transport` e opcional e usado apenas em testes (ex: httpx.MockTransport)
    para simular respostas reais (incluindo compressao) sem rede.
    """
    method = request_def.get("method", "GET").upper()
    url = request_def["url"]
    base_url, query_from_url = split_url_query(url)
    kwargs = build_httpx_request_kwargs(request_def)
    # query_params explicito (editor de query params / auth api_key em query)
    # tem precedencia sobre o que ja estava embutido no texto da URL.
    kwargs["params"] = {**query_from_url, **kwargs["params"]}

    start = time.perf_counter()
    error: str | None = None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, transport=transport) as client:
            response = client.request(method, base_url, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        status_code = response.status_code
        resp_headers = dict(response.headers)
        body_raw = response.text
        content_type = response.headers.get("content-type", "")
        body_json = None
        json_valid = False
        try:
            body_json = response.json()
            json_valid = True
        except Exception:
            json_valid = False
    except httpx.RequestError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        status_code = None
        resp_headers = {}
        body_raw = ""
        content_type = ""
        body_json = None
        json_valid = False
        error = f"{type(exc).__name__}: {exc}"

    return {
        "method": method,
        "url": url,
        "status_code": status_code,
        "headers": resp_headers,
        "content_type": content_type,
        "body_raw": body_raw,
        "body_json": body_json,
        "json_valid": json_valid,
        "response_time_ms": round(elapsed_ms, 2),
        "error": error,
    }
