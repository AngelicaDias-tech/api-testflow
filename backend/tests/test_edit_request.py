"""
Edicao de API ja cadastrada (secao 30 do pedido) - cobre especificamente a
protecao de segredos ao atualizar: como a interface nunca reenvia o valor
mascarado como se fosse o segredo real, campos sensiveis chegam em branco
no PUT quando o usuario nao quis altera-los, e `carry_over_blank_secrets`
(app/core/security.py) e quem garante que o segredo real (ja criptografado)
e preservado nesse caso - sem isso, editar qualquer outro campo (ex: nome)
sem tocar no token apagaria a autenticacao Bearer/API Key/Personalizada/
Basic ja configurada.
"""

from __future__ import annotations

from app.core.security import (
    carry_over_blank_secrets,
    decrypt_value,
    encrypt_auth_for_storage,
    encrypt_headers_for_storage,
    is_sensitive_auth_field,
    is_sensitive_header,
)


def test_campo_sensivel_em_branco_preserva_valor_criptografado_existente():
    old_auth = encrypt_auth_for_storage({"type": "bearer", "token": "token-original"})
    new_auth = encrypt_auth_for_storage({"type": "bearer", "token": ""})

    merged = carry_over_blank_secrets(new_auth, old_auth, is_sensitive_auth_field)

    assert decrypt_value(merged["token"]) == "token-original"


def test_campo_sensivel_preenchido_substitui_o_valor_existente():
    old_auth = encrypt_auth_for_storage({"type": "bearer", "token": "token-original"})
    new_auth = encrypt_auth_for_storage({"type": "bearer", "token": "token-novo"})

    merged = carry_over_blank_secrets(new_auth, old_auth, is_sensitive_auth_field)

    assert decrypt_value(merged["token"]) == "token-novo"


def test_campo_nao_sensivel_em_branco_nao_e_afetado():
    old_auth = encrypt_auth_for_storage({"type": "api_key", "key_name": "X-API-Key", "api_key": "abc123"})
    new_auth = encrypt_auth_for_storage({"type": "api_key", "key_name": "", "api_key": ""})

    merged = carry_over_blank_secrets(new_auth, old_auth, is_sensitive_auth_field)

    # key_name nao e sensivel - o valor em branco enviado pelo usuario prevalece.
    assert merged["key_name"] == ""
    # api_key e sensivel e veio em branco - preserva o valor real existente.
    assert decrypt_value(merged["api_key"]) == "abc123"


def test_sem_valor_antigo_para_o_mesmo_campo_fica_em_branco():
    old_auth = encrypt_auth_for_storage({"type": "none"})
    new_auth = encrypt_auth_for_storage({"type": "bearer", "token": ""})

    merged = carry_over_blank_secrets(new_auth, old_auth, is_sensitive_auth_field)

    assert merged["token"] == ""


def test_header_sensivel_em_branco_preserva_valor_existente():
    old_headers = encrypt_headers_for_storage({"Authorization": "Bearer token-original", "Accept": "application/json"})
    new_headers = encrypt_headers_for_storage({"Authorization": "", "Accept": "application/xml"})

    merged = carry_over_blank_secrets(new_headers, old_headers, is_sensitive_header)

    assert decrypt_value(merged["Authorization"]) == "Bearer token-original"
    assert merged["Accept"] == "application/xml"


def test_nenhum_valor_antigo_retorna_novo_dict_intacto():
    new_values = {"token": ""}
    assert carry_over_blank_secrets(new_values, None, is_sensitive_auth_field) == new_values
    assert carry_over_blank_secrets(new_values, {}, is_sensitive_auth_field) == new_values
