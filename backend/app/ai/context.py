"""
Montagem de contexto para a IA (melhoria "Integração contextual da IA").

Por que existe: TODA rota de app/api/ai.py que recebe um `response_ctx`
vindo do frontend precisa mascarar headers sensíveis antes de montar
qualquer prompt/payload para um provider (heurístico ou OpenAI) - isso já
era feito, mas repetido (copiado/colado) em cada rota. Centralizar aqui:

  1. evita que uma rota nova esqueça de mascarar (o erro mais caro
     possível nesta área - vazar um Authorization/Cookie para um provider
     de IA, inclusive um provider de nuvem no futuro);
  2. documenta em UM lugar só o que é "contexto mínimo necessário" pra IA,
     em vez de cada rota decidir isso sozinha.

Nunca inclui um campo que não foi fornecido (evita mandar `null`/`{}` para
o prompt à toa) - "não enviar informação desnecessária para o modelo" é um
requisito explícito, não só um detalhe de implementação.
"""

from __future__ import annotations

from typing import Any

from app.core.security import mask_headers

# Chaves de response_ctx que, quando presentes, sao seguras para mandar
# como estao (nenhuma delas carrega segredo) - todo o resto (ex: um campo
# extra desconhecido que o frontend mande por engano) e descartado por
# padrao, nunca repassado "as cegas" para um provider de IA.
_SAFE_RESPONSE_CTX_KEYS = (
    "status_code",
    "content_type",
    "response_time_ms",
    "json_valid",
    "body_json",
    "error",
)


def mask_response_ctx(response_ctx: dict[str, Any] | None) -> dict[str, Any] | None:
    """Aplica a MESMA regra de mascaramento de headers em qualquer
    response_ctx antes de ele seguir para um AIProvider. `None` continua
    `None` (nem toda rota tem uma resposta real ainda)."""
    if not response_ctx:
        return response_ctx
    ctx = dict(response_ctx)
    if "headers" in ctx:
        ctx["headers"] = mask_headers(ctx.get("headers") or {})
    return ctx


def build_chat_context(
    *,
    method: str | None = None,
    url: str | None = None,
    response_ctx: dict[str, Any] | None = None,
    rules: list[dict] | None = None,
    execution_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta o contexto do Assistente de IA (chat) a partir das peças que
    o frontend tem disponíveis na tela atual (Workbench/Execution) -
    method/url da API, a última resposta observada (já mascarada), as
    regras já aprovadas (só campo/operador/valor - nunca um objeto Rule
    completo do banco) e, quando a pergunta parte de um resultado de teste
    específico, o resultado (`execution_result`: field/operator/expected/
    actual/outcome). Só inclui o que foi de fato passado."""
    ctx: dict[str, Any] = {}
    if method:
        ctx["method"] = method
    if url:
        ctx["url"] = url
    masked = mask_response_ctx(response_ctx)
    if masked:
        for key in _SAFE_RESPONSE_CTX_KEYS:
            if key in masked and masked[key] is not None:
                ctx[key] = masked[key]
        if masked.get("headers"):
            ctx["headers"] = masked["headers"]
    if rules:
        ctx["rules"] = [
            {"field": r.get("field"), "operator": r.get("operator"), "expected": r.get("expected")} for r in rules
        ]
    if execution_result:
        ctx["execution_result"] = execution_result
    return ctx
