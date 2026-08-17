"""
Substituicao de placeholders `{{variavel}}` (melhorias "Cenarios de teste" e
"Massas de teste via CSV"). Modulo unico e compartilhado pelos dois fluxos -
um cenario manual e uma linha de uma massa CSV sao, tecnicamente, a MESMA
operacao: um dict de variaveis substituindo `{{var}}` dentro da definicao de
request (e, opcionalmente, dentro do valor esperado de uma regra), antes de
chamar `app.engine.http_executor.execute_request`/`app.engine.pytest_runner.
run_pytest` normalmente. Nao existe um motor de execucao paralelo - cenario
e massa só preparam o `request_def`/`checks` de entrada.
"""

from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def find_placeholders(text: str) -> set[str]:
    """Nomes de variaveis `{{var}}` referenciadas em um texto (sem duplicar)."""
    if not text:
        return set()
    return set(_PLACEHOLDER_RE.findall(text))


def render_template(text: str | None, variables: dict[str, Any]) -> str | None:
    """Substitui `{{var}}` pelo valor de `variables["var"]` (convertido para
    string). Uma variavel referenciada mas ausente do dict e deixada como
    esta (nunca vira uma string vazia silenciosamente) - isso torna erros de
    massa/cenario visiveis em vez de mascarados."""
    if text is None:
        return None

    def _sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in variables:
            return match.group(0)
        value = variables[name]
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return _PLACEHOLDER_RE.sub(_sub, text)


def render_request_def(request_def: dict, variables: dict[str, Any]) -> dict:
    """Aplica `render_template` a URL, headers, query params e body de uma
    definicao de request - usado tanto por um cenario manual quanto por
    cada linha de uma massa. Nao muta o dict original (o request salvo no
    banco nunca é alterado por um cenario/massa - ver requisito explícito)."""
    resolved = dict(request_def)
    resolved["url"] = render_template(request_def.get("url", ""), variables)
    resolved["body"] = render_template(request_def.get("body"), variables)
    resolved["headers"] = {
        k: render_template(v, variables) for k, v in (request_def.get("headers") or {}).items()
    }
    resolved["query_params"] = {
        k: render_template(v, variables) for k, v in (request_def.get("query_params") or {}).items()
    }
    return resolved


def render_checks(checks: list[dict], variables: dict[str, Any]) -> list[dict]:
    """Aplica `render_template` a `expected`/`condition_expected` de cada
    check QUANDO esses campos contiverem `{{var}}` - permite que a MESMA
    regra ja aprovada (ex: "status equals {{resultado_esperado}}") seja
    reaproveitada por varios cenarios/linhas de massa com um valor esperado
    diferente em cada execucao. Regras "normais" (sem placeholder) saem
    identicas - comportamento existente preservado."""
    resolved = []
    for check in checks:
        new_check = dict(check)
        for field in ("expected", "condition_expected"):
            value = check.get(field)
            if isinstance(value, str) and "{{" in value:
                new_check[field] = render_template(value, variables)
        resolved.append(new_check)
    return resolved
