"""
Importador de cURL (secao 5 do spec).

Por que existe: squads copiam requisicoes de ferramentas como Postman,
Bruno, DevTools do navegador ou logs, quase sempre como comando cURL. Em
vez de exigir que o usuario preencha metodo/headers/body manualmente,
convertendo o cURL automaticamente, o primeiro teste fica a poucos
segundos de distancia. O usuario ainda revisa tudo antes de executar
(nenhuma requisicao e disparada sem confirmacao explicita).
"""

from __future__ import annotations

import shlex
from urllib.parse import parse_qsl, urlparse, urlunparse


class CurlParseError(ValueError):
    pass


def parse_curl(curl_command: str) -> dict:
    text = curl_command.strip()
    if not text:
        raise CurlParseError("Comando cURL vazio")
    # normaliza continuacao de linha estilo bash/powershell (\ ou ` no fim da linha)
    text = text.replace("`\n", " ").replace("\\\n", " ").replace("\\\r\n", " ")

    try:
        tokens = shlex.split(text, posix=True)
    except ValueError as exc:
        raise CurlParseError(f"Nao foi possivel interpretar o cURL: {exc}") from exc

    if not tokens or tokens[0] != "curl":
        if tokens and tokens[0] == "curl":
            pass
        else:
            raise CurlParseError("O comando deve comecar com 'curl'")

    method: str | None = None
    url: str | None = None
    headers: dict[str, str] = {}
    data_parts: list[str] = []
    is_form = False
    basic_user: str | None = None

    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-X", "--request"):
            i += 1
            method = tokens[i].upper()
        elif tok in ("-H", "--header"):
            i += 1
            header_line = tokens[i]
            if ":" in header_line:
                name, value = header_line.split(":", 1)
                headers[name.strip()] = value.strip()
        elif tok in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"):
            i += 1
            data_parts.append(tokens[i])
            if method is None:
                method = "POST"
        elif tok == "--form" or tok == "-F":
            i += 1
            data_parts.append(tokens[i])
            is_form = True
            if method is None:
                method = "POST"
        elif tok in ("-u", "--user"):
            i += 1
            basic_user = tokens[i]
        elif tok in ("-b", "--cookie"):
            i += 1
            headers["Cookie"] = tokens[i]
        elif tok in (
            "--location", "-L", "-s", "--silent", "-k", "--insecure", "-i", "--include", "-G", "--compressed",
        ):
            pass
        elif tok == "--url":
            i += 1
            url = tokens[i]
        elif tok.startswith("-"):
            # flag desconhecida - ignora com seguranca (nao interrompe o import)
            pass
        else:
            if url is None:
                url = tok
        i += 1

    if not url:
        raise CurlParseError("Nao foi possivel identificar a URL no comando cURL")

    method = method or "GET"

    body: str | None = None
    body_type = "none"
    if data_parts:
        if is_form:
            body = "&".join(data_parts)
            body_type = "text"
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = "&".join(data_parts) if len(data_parts) > 1 else data_parts[0]
            body_type = "json" if _looks_like_json(body) else "text"

    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query))
    clean_url = urlunparse(parsed._replace(query=""))

    auth: dict = {"type": "none"}
    if basic_user:
        if ":" in basic_user:
            username, password = basic_user.split(":", 1)
        else:
            username, password = basic_user, ""
        auth = {"type": "basic", "username": username, "password": password}
    elif "Authorization" in headers:
        auth_header = headers.pop("Authorization")
        if auth_header.lower().startswith("bearer "):
            auth = {"type": "bearer", "token": auth_header[7:].strip()}
        else:
            headers["Authorization"] = auth_header  # esquema nao reconhecido, mantem como header

    return {
        "method": method,
        "url": clean_url,
        "headers": headers,
        "query_params": query_params,
        "body": body,
        "body_type": body_type,
        "auth": auth,
    }


def _looks_like_json(text: str) -> bool:
    text = text.strip()
    return (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]"))
