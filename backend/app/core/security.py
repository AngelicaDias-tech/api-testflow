"""
Protecao de segredos (secao 29 do spec).

Por que existe: headers de autenticacao (Authorization, API keys, cookies)
e credenciais de basic auth nao podem ficar em texto puro no banco nem
aparecer completos na UI ou serem enviados para a IA. Este modulo cuida de:

  1. Criptografar valores sensiveis antes de persistir (Fernet/AES simetrico).
  2. Descriptografar apenas no momento de montar a requisicao HTTP real.
  3. Mascarar valores sensiveis quando exibidos na interface ou enviados
     para o provedor de IA (nunca o valor completo).
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.config import get_settings

_SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "x-auth-token",
    "proxy-authorization",
}
_SENSITIVE_AUTH_FIELDS = {"token", "password", "api_key", "secret"}

_DEFAULT_KEY_FILE = Path(__file__).resolve().parent.parent.parent / ".secret_key"
_KEY_FILE = Path(os.getenv("API_TESTFLOW_SECRET_KEY_FILE") or _DEFAULT_KEY_FILE)


def _load_or_create_key() -> bytes:
    settings = get_settings()
    if settings.secret_key:
        return settings.secret_key.encode() if len(settings.secret_key) >= 44 else Fernet.generate_key()
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    return key


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def encrypt_value(value: str) -> str:
    if not value:
        return value
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    if not token:
        return token
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except Exception:
        # Valor nao criptografado (ex: dado legado) - retorna como esta.
        return token


def is_sensitive_header(name: str) -> bool:
    return name.strip().lower() in _SENSITIVE_HEADER_NAMES


def is_sensitive_auth_field(name: str) -> bool:
    return name.strip().lower() in _SENSITIVE_AUTH_FIELDS


def mask_value(value: str, keep_prefix: int = 6) -> str:
    if not value:
        return value
    if len(value) <= keep_prefix:
        return "*" * len(value)
    return f"{value[:keep_prefix]}{'*' * 8}"


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        k: (mask_value(v) if is_sensitive_header(k) else v)
        for k, v in (headers or {}).items()
    }


def encrypt_headers_for_storage(headers: dict[str, str]) -> dict[str, str]:
    return {
        k: (encrypt_value(v) if is_sensitive_header(k) and v else v)
        for k, v in (headers or {}).items()
    }


def decrypt_headers_for_request(headers: dict[str, str]) -> dict[str, str]:
    return {
        k: (decrypt_value(v) if is_sensitive_header(k) and v else v)
        for k, v in (headers or {}).items()
    }


def encrypt_auth_for_storage(auth: dict | None) -> dict | None:
    if not auth:
        return auth
    out = dict(auth)
    for k, v in out.items():
        if is_sensitive_auth_field(k) and isinstance(v, str) and v:
            out[k] = encrypt_value(v)
    return out


def mask_auth(auth: dict | None) -> dict | None:
    if not auth:
        return auth
    masked = dict(auth)
    for k, v in masked.items():
        if is_sensitive_auth_field(k) and isinstance(v, str):
            masked[k] = mask_value(v)
    return masked
