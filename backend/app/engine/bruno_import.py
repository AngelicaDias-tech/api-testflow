"""
Importador de requisicoes Bruno (secao 6 do spec).

Escopo desta implementacao (decisao deliberada, ver secao 6):

Bruno salva cada requisicao como um arquivo texto `.bru` em formato de
blocos (`meta {...}`, `get {...}`, `headers {...}`, `body:json {...}`,
`auth:bearer {...}` etc.) - este e o formato REAL gerado pelo proprio
Bruno ao salvar uma requisicao em disco, nao um formato inventado aqui.

O QUE SUPORTAMOS: importar um arquivo `.bru` de uma UNICA requisicao
(o caso comum de "exportar/copiar uma requisicao do Bruno para revisar
em outra ferramenta"): metodo, URL, query params, headers, body
(json/text/graphql) e auth (bearer/basic/apikey).

O QUE NAO SUPORTAMOS AINDA: importacao de uma COLLECTION inteira do
Bruno (multiplas pastas/arquivos + `bruno.json` + arquivos de
environment). Isso exigiria resolver variaveis `{{var}}` atraves de um
grafo de arquivos de ambiente/coleção, o que e significativamente mais
complexo do que analisar uma unica requisicao. Em vez de inventar um
comportamento parcial e confuso para isso, preferimos:
  1. suportar bem o caso de uma requisicao unica, e
  2. detectar variaveis `{{...}}` nao resolvidas e avisar claramente o
     usuario na revisao, para que ele preencha o valor manualmente antes
     de executar o teste.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlparse, urlunparse

_BLOCK_START_RE = re.compile(r"^([A-Za-z][\w:.\-]*)\s*\{\s*$")
_HTTP_VERBS = {"get", "post", "put", "patch", "delete", "options", "head"}
_VAR_RE = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")


class BrunoParseError(ValueError):
    pass


def _parse_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    current: str | None = None
    depth = 0
    buffer: list[str] = []

    for raw_line in text.splitlines():
        if current is None:
            m = _BLOCK_START_RE.match(raw_line.strip())
            if m:
                current = m.group(1)
                depth = 1
                buffer = []
            continue
        open_count = raw_line.count("{")
        close_count = raw_line.count("}")
        new_depth = depth + open_count - close_count
        if new_depth <= 0:
            blocks[current] = "\n".join(buffer)
            current = None
            depth = 0
        else:
            buffer.append(raw_line)
            depth = new_depth

    return blocks


def _parse_kv(block_text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in block_text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        enabled = True
        if key.startswith("~"):
            key = key[1:].strip()
            enabled = False
        if not enabled:
            continue  # entrada desabilitada no Bruno (prefixo ~)
        result[key] = value.strip()
    return result


def parse_bru(text: str) -> dict:
    """Converte o conteudo de um arquivo `.bru` de uma requisicao no
    formato normalizado usado pelo restante do sistema."""
    if "{" not in text:
        raise BrunoParseError("Conteudo nao parece um arquivo .bru valido")

    blocks = _parse_blocks(text)

    method_block_name = next((b for b in blocks if b in _HTTP_VERBS), None)
    if not method_block_name:
        raise BrunoParseError(
            "Nao foi encontrado um bloco de metodo HTTP (get/post/put/patch/delete) no arquivo .bru"
        )

    method_kv = _parse_kv(blocks[method_block_name])
    raw_url = method_kv.get("url", "")
    if not raw_url:
        raise BrunoParseError("Bloco de metodo nao contem 'url'")

    parsed = urlparse(raw_url)
    query_params = dict(parse_qsl(parsed.query))
    url = urlunparse(parsed._replace(query=""))

    if "query" in blocks or "params:query" in blocks:
        query_params.update(_parse_kv(blocks.get("query") or blocks.get("params:query", "")))

    headers = _parse_kv(blocks.get("headers", ""))

    body_ref = method_kv.get("body", "none").strip()
    body: str | None = None
    body_type = "none"
    if body_ref == "json" and "body:json" in blocks:
        body = blocks["body:json"].strip()
        body_type = "json"
    elif body_ref == "text" and "body:text" in blocks:
        body = blocks["body:text"].strip()
        body_type = "text"
    elif body_ref == "graphql" and "body:graphql" in blocks:
        body = blocks["body:graphql"].strip()
        body_type = "text"
    elif body_ref == "xml" and "body:xml" in blocks:
        body = blocks["body:xml"].strip()
        body_type = "text"

    auth: dict = {"type": "none"}
    auth_ref = method_kv.get("auth", "none").strip()
    if auth_ref == "bearer" and "auth:bearer" in blocks:
        kv = _parse_kv(blocks["auth:bearer"])
        auth = {"type": "bearer", "token": kv.get("token", "")}
    elif auth_ref == "basic" and "auth:basic" in blocks:
        kv = _parse_kv(blocks["auth:basic"])
        auth = {"type": "basic", "username": kv.get("username", ""), "password": kv.get("password", "")}
    elif auth_ref == "apikey" and "auth:apikey" in blocks:
        kv = _parse_kv(blocks["auth:apikey"])
        auth = {
            "type": "api_key",
            "key_name": kv.get("key", "X-API-Key"),
            "api_key": kv.get("value", ""),
            "location": "query" if kv.get("placement") == "queryparams" else "header",
        }

    unresolved_vars = sorted(set(_VAR_RE.findall(text)))

    meta_kv = _parse_kv(blocks.get("meta", ""))

    return {
        "name": meta_kv.get("name", "Requisicao importada do Bruno"),
        "method": method_block_name.upper(),
        "url": url,
        "headers": headers,
        "query_params": query_params,
        "body": body,
        "body_type": body_type,
        "auth": auth,
        "unresolved_variables": unresolved_vars,
    }
