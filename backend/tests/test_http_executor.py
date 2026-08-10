"""
Regressao: uma API que (a) retorna a resposta comprimida (Content-Encoding:
deflate/gzip) e (b) recebe query params embutidos diretamente na URL (em vez
de um dict `query_params` separado) precisa continuar funcionando.

Bug real observado com a Open-Meteo: o backend chamava
`httpx.Client.request(url, params=query_params)` e, quando `query_params`
estava vazio ({}) mas a URL já tinha `?latitude=...&longitude=...`, o
httpx SUBSTITUÍA a query da URL pelo dict vazio - a API então recebia uma
chamada sem nenhum parâmetro, respondia 200 com um corpo mínimo, e o
TestFlow mostrava "não é JSON" / body vazio. Isso não tinha relação com a
descompressão em si (httpx já descomprime deflate/gzip automaticamente) -
era a query sendo apagada antes da chamada.
"""

from __future__ import annotations

import gzip
import zlib

import httpx

from app.engine.http_executor import execute_request, split_url_query

WEATHER_PAYLOAD = b'{"latitude": 52.52, "longitude": 13.41, "current_weather": {"temperature": 21.4}}'


def _make_transport(compress: str | None, capture: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        capture["url"] = str(request.url)
        headers = {"content-type": "application/json; charset=utf-8"}
        if compress == "deflate":
            body = zlib.compress(WEATHER_PAYLOAD)
            headers["content-encoding"] = "deflate"
        elif compress == "gzip":
            body = gzip.compress(WEATHER_PAYLOAD)
            headers["content-encoding"] = "gzip"
        else:
            body = WEATHER_PAYLOAD
        return httpx.Response(200, headers=headers, content=body)

    return httpx.MockTransport(handler)


def test_split_url_query_extracts_and_strips_query():
    base, query = split_url_query("https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41")
    assert base == "https://api.open-meteo.com/v1/forecast"
    assert query == {"latitude": "52.52", "longitude": "13.41"}


def test_split_url_query_no_query_string():
    base, query = split_url_query("https://api.open-meteo.com/v1/forecast")
    assert base == "https://api.open-meteo.com/v1/forecast"
    assert query == {}


def test_execute_request_preserves_query_embedded_in_url_with_deflate_body():
    capture: dict = {}
    transport = _make_transport("deflate", capture)
    request_def = {
        "method": "GET",
        "url": "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true",
        "headers": {},
        "query_params": {},  # dict vazio - era esse o gatilho do bug
        "body": None,
        "body_type": "none",
        "auth": {"type": "none"},
    }

    ctx = execute_request(request_def, timeout=5, transport=transport)

    assert ctx["error"] is None
    assert ctx["status_code"] == 200
    assert ctx["json_valid"] is True
    assert ctx["body_json"] == {"latitude": 52.52, "longitude": 13.41, "current_weather": {"temperature": 21.4}}
    assert ctx["body_raw"]  # body preservado, nao vazio

    # a query original nao pode ter sido apagada antes da chamada real
    assert "latitude=52.52" in capture["url"]
    assert "longitude=13.41" in capture["url"]
    assert "current_weather=true" in capture["url"]


def test_execute_request_decompresses_gzip_body_too():
    capture: dict = {}
    transport = _make_transport("gzip", capture)
    request_def = {
        "method": "GET",
        "url": "https://api.example.com/data",
        "headers": {},
        "query_params": {},
        "body": None,
        "body_type": "none",
        "auth": {"type": "none"},
    }

    ctx = execute_request(request_def, timeout=5, transport=transport)

    assert ctx["json_valid"] is True
    assert ctx["body_json"]["current_weather"]["temperature"] == 21.4


def test_execute_request_works_uncompressed_too():
    capture: dict = {}
    transport = _make_transport(None, capture)
    request_def = {
        "method": "GET",
        "url": "https://api.example.com/data?x=1",
        "headers": {},
        "query_params": {},
        "body": None,
        "body_type": "none",
        "auth": {"type": "none"},
    }

    ctx = execute_request(request_def, timeout=5, transport=transport)

    assert ctx["json_valid"] is True
    assert "x=1" in capture["url"]


def test_explicit_query_params_override_url_on_conflict():
    capture: dict = {}
    transport = _make_transport(None, capture)
    request_def = {
        "method": "GET",
        "url": "https://api.example.com/data?latitude=0",
        "headers": {},
        "query_params": {"latitude": "52.52"},
        "body": None,
        "body_type": "none",
        "auth": {"type": "none"},
    }

    execute_request(request_def, timeout=5, transport=transport)

    assert "latitude=52.52" in capture["url"]
    assert "latitude=0" not in capture["url"]
