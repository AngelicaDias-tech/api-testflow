"""Mensagens de erro amigaveis (melhoria 1). Cobre: mapeamento por status
HTTP, classificacao de erros de transporte httpx e o scrub de credenciais
que possam ter sido coladas manualmente na URL."""

from __future__ import annotations

import httpx

from app.core.error_messages import (
    friendly_status_message,
    friendly_transport_error,
    internal_error_message,
    validation_error_message,
)


def test_friendly_status_message_covers_documented_codes():
    assert "token" in friendly_status_message(401).lower()
    assert "permiss" in friendly_status_message(403).lower()
    assert "não encontrado" in friendly_status_message(404).lower()
    assert "limite de uso" in friendly_status_message(429).lower()
    assert "servidor testado" in friendly_status_message(500).lower()


def test_friendly_status_message_none_for_success():
    assert friendly_status_message(200) is None
    assert friendly_status_message(301) is None
    assert friendly_status_message(None) is None


def test_friendly_status_message_falls_back_by_family():
    msg = friendly_status_message(418)  # codigo incomum, sem entrada fixa
    assert "418" in msg


def test_friendly_transport_error_timeout():
    exc = httpx.ConnectTimeout("timed out")
    friendly, detail = friendly_transport_error(exc)
    assert "tempo limite" in friendly.lower()
    assert "ConnectTimeout" in detail


def test_friendly_transport_error_connect_error():
    exc = httpx.ConnectError("Connection refused")
    friendly, detail = friendly_transport_error(exc)
    assert "conectar" in friendly.lower()


def test_friendly_transport_error_scrubs_credentials_from_detail():
    exc = httpx.ConnectError("failed for https://api.example.com/x?token=abcDEF123&other=1")
    _friendly, detail = friendly_transport_error(exc)
    assert "abcDEF123" not in detail
    assert "********" in detail


def test_internal_error_message_never_leaks_exception_text():
    msg = internal_error_message("executar os testes")
    assert "TestFlow" in msg
    assert "Traceback" not in msg


def test_validation_error_message_aggregates_fields():
    errors = [
        {"loc": ("body", "url"), "msg": "field required"},
        {"loc": ("body", "method"), "msg": "field required"},
    ]
    msg = validation_error_message(errors)
    assert "url" in msg
    assert "method" in msg
