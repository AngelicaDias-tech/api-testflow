"""
Mensagens de erro amigaveis (melhoria 1 do roadmap).

Por que existe separado: tanto o probe (app/api/requests.py) quanto a
execucao de testes (app/api/executions.py) e futuramente cenarios/massas
precisam da MESMA logica de "traduzir" um erro tecnico (excecao httpx,
codigo HTTP devolvido pela API testada, JSON invalido...) em uma frase que
faca sentido pra quem nao é dev. Centralizar aqui evita reescrever a mesma
seleção de mensagens em cada rota.

Regra de seguranca: nenhuma funcao aqui deve jamais interpolar um header
sensivel, token, senha ou trecho de URL com credenciais na mensagem
devolvida ao usuario - `_scrub_secrets` cobre o caso residual de alguem
colar um token dentro da propria URL (fora do fluxo de auth recomendado).
"""

from __future__ import annotations

import re

import httpx

_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|token|password|senha|secret|api[_-]?key|apikey)=([^&\s]+)"
)
_QUERY_PATTERN = re.compile(r"\?[^\s\"']+")


def _scrub_secrets(text: str) -> str:
    """Remove padroes 'chave=valor' que parecam credencial e query strings
    inteiras (podem conter um token colado manualmente na URL, fora do
    editor de autenticacao) de uma mensagem tecnica antes de ela ser
    exibida ou logada."""
    if not text:
        return text
    text = _SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=********", text)
    text = _QUERY_PATTERN.sub("?********", text)
    return text


HTTP_STATUS_MESSAGES: dict[int, str] = {
    400: "A API recusou a requisição por dados inválidos. Confira o body, os parâmetros e os headers enviados.",
    401: "Não autorizado. Verifique se o token está correto, válido e não expirado (ou se falta configurar "
    "autenticação para esta API).",
    403: "Acesso negado. O token foi reconhecido, mas não possui permissão para acessar este recurso.",
    404: "Recurso não encontrado. Verifique se a URL e os parâmetros (ex: ID) estão corretos.",
    405: "Método HTTP não permitido para esta URL. Confirme se o método (GET/POST/...) está correto.",
    408: "A própria API sinalizou timeout ao processar a requisição.",
    409: "Conflito ao processar a requisição — o estado atual do recurso não permite esta operação.",
    422: "A API recusou os dados enviados por não passarem na validação dela. Confira o formato do body/params.",
    429: "Muitas requisições em pouco tempo. A API aplicou limite de uso (rate limit) — aguarde e tente "
    "novamente.",
    500: "A API encontrou um erro interno. O problema é do lado do servidor testado, não do TestFlow.",
    502: "A API (ou um serviço do qual ela depende) respondeu de forma inválida (Bad Gateway).",
    503: "A API está indisponível ou sobrecarregada no momento (Service Unavailable).",
    504: "A API (ou um serviço do qual ela depende) demorou demais para responder (Gateway Timeout).",
}

_STATUS_FAMILY_FALLBACK: dict[int, str] = {
    4: "A API recusou esta requisição (erro {status}). Confira os dados enviados e a autenticação.",
    5: "A API testada teve um problema ao processar esta requisição (erro {status}). O problema é do lado dela, "
    "não do TestFlow.",
}


def friendly_status_message(status_code: int | None) -> str | None:
    """Mensagem amigavel para o STATUS CODE devolvido pela API testada.
    Retorna None para respostas 2xx/3xx normais (nao ha nada a explicar)."""
    if status_code is None or status_code < 400:
        return None
    if status_code in HTTP_STATUS_MESSAGES:
        return HTTP_STATUS_MESSAGES[status_code]
    family = status_code // 100
    template = _STATUS_FAMILY_FALLBACK.get(family)
    if template:
        return template.format(status=status_code)
    return f"A API respondeu com o código HTTP {status_code}."


def friendly_transport_error(exc: Exception) -> tuple[str, str]:
    """Classifica uma excecao de TRANSPORTE (o TestFlow nem chegou a ter uma
    resposta HTTP) em (mensagem amigavel, detalhe tecnico mascarado).

    Isso e sempre um problema de CONECTIVIDADE/URL, nunca um status HTTP da
    API testada - por isso vive separado de `friendly_status_message`.
    """
    detail = _scrub_secrets(f"{type(exc).__name__}: {exc}")

    if isinstance(exc, httpx.ConnectTimeout | httpx.ReadTimeout | httpx.WriteTimeout | httpx.PoolTimeout):
        return (
            "A API não respondeu dentro do tempo limite configurado. Ela pode estar lenta, sobrecarregada ou fora "
            "do ar.",
            detail,
        )
    if isinstance(exc, httpx.TimeoutException):
        return ("A chamada excedeu o tempo limite configurado.", detail)
    if isinstance(exc, httpx.ConnectError):
        return (
            "Não foi possível conectar a esta API. Verifique se o endereço está correto e se o serviço está "
            "acessível a partir daqui.",
            detail,
        )
    if isinstance(exc, httpx.UnsupportedProtocol | httpx.InvalidURL):
        return (
            "A URL informada não é válida. Verifique o protocolo (http/https) e o formato do endereço.",
            detail,
        )
    if isinstance(exc, httpx.TooManyRedirects):
        return ("A API entrou em um loop de redirecionamentos ao processar esta requisição.", detail)
    if isinstance(exc, httpx.RequestError):
        return (
            "Não foi possível completar a chamada a esta API (falha de conexão/rede).",
            detail,
        )
    return ("Ocorreu um erro inesperado ao tentar chamar esta API.", detail)


def internal_error_message(context: str = "") -> str:
    """Mensagem para um erro INTERNO do TestFlow (nao da API testada nem de
    rede) - ex: falha ao rodar o subprocesso pytest. Deliberadamente sem
    detalhe tecnico na resposta ao usuario; o detalhe vai para o console do
    servidor (`print`), nunca para o payload HTTP nem para o banco exposto
    via API."""
    base = "Ocorreu um erro interno no TestFlow"
    if context:
        base += f" ao {context}"
    return base + ". Tente novamente; se persistir, contate o time responsável."


def validation_error_message(errors: list[dict]) -> str:
    """Mensagem agregada e amigavel para erros de validacao de payload
    (ex: RequestValidationError do FastAPI/Pydantic) - mantem o campo e o
    motivo (util pro diagnostico) sem expor a estrutura interna crua."""
    if not errors:
        return "Dados inválidos enviados nesta requisição."
    parts = []
    for err in errors[:6]:
        loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
        msg = err.get("msg", "valor inválido")
        parts.append(f"'{loc}': {msg}" if loc else msg)
    joined = "; ".join(parts)
    return f"Dados inválidos: {joined}."
