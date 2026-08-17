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

from app.core.error_messages import friendly_transport_error
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


def _auth_sensitive_keys(auth: dict) -> tuple[set[str], set[str]]:
    """Devolve (nomes de HEADER, nomes de QUERY PARAM) que uma definicao de
    auth escreve com um valor secreto - usado só para saber o que MASCARAR
    ao montar `build_sent_snapshot`. Existe separado de
    `build_httpx_request_kwargs` para nao alterar a assinatura dessa funcao
    (contrato coberto por tests/test_auth.py) - é um espelho pequeno e
    deliberadamente redundante da mesma decisao de "onde a auth escreve",
    não uma segunda forma de montar o request real."""
    auth_type = (auth or {}).get("type", "none")
    if auth_type == "bearer":
        return {"Authorization"}, set()
    if auth_type == "api_key":
        key_name = auth.get("key_name", "X-API-Key")
        location = auth.get("location", "header")
        return ({key_name}, set()) if location != "query" else (set(), {key_name})
    if auth_type == "custom":
        key_name = auth.get("key_name", "")
        return ({key_name} if key_name else set()), set()
    if auth_type == "basic":
        return {"Authorization"}, set()
    return set(), set()


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


def build_sent_snapshot(request_def: dict) -> dict:
    """Descreve o request EFETIVAMENTE montado (metodo, URL final com query
    resolvida, headers finais, body) para exibicao na UI ("Request
    enviado" - melhoria 2), sempre com valores sensiveis mascarados.

    Funcao pura, sem chamada de rede - reaproveita a MESMA logica de
    montagem usada pela chamada real (`build_httpx_request_kwargs`), entao
    o que a UI mostra nunca diverge do que de fato seria enviado.
    """
    from app.core.security import mask_headers, mask_value  # import local: evita ciclo em modulo pequeno

    method = request_def.get("method", "GET").upper()
    url = request_def.get("url", "")
    base_url, query_from_url = split_url_query(url)
    kwargs = build_httpx_request_kwargs(request_def)
    sensitive_header_keys, sensitive_query_keys = _auth_sensitive_keys(request_def.get("auth") or {})
    merged_params = {**query_from_url, **kwargs["params"]}

    masked_headers = mask_headers(kwargs["headers"])
    for key in sensitive_header_keys:
        if key in kwargs["headers"] and kwargs["headers"][key]:
            masked_headers[key] = mask_value(kwargs["headers"][key])
    if "auth" in kwargs:  # basic auth: httpx monta o header, nao aparece em kwargs["headers"]
        masked_headers["Authorization"] = "Basic ********"

    masked_params = dict(merged_params)
    for key in sensitive_query_keys:
        if key in masked_params:
            masked_params[key] = mask_value(masked_params[key]) if masked_params[key] else "********"

    body = request_def.get("body")
    body_type = request_def.get("body_type", "none")

    return {
        "method": method,
        "url": base_url,
        "query_params": masked_params,
        "headers": masked_headers,
        "auth_type": (request_def.get("auth") or {}).get("type", "none"),
        "body": body if body_type != "none" else None,
        "body_type": body_type,
    }


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
    error_detail: str | None = None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, transport=transport, verify=False) as client:
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
        error, error_detail = friendly_transport_error(exc)

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
        "error_detail": error_detail,
    }
