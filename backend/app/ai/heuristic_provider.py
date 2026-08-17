"""
Provedor de IA padrao: heuristico, 100% local, sem dependencias externas
e sem custo (secao 12, 28 e 29). E o que garante que "o sistema deve
funcionar normalmente sem IA" na pratica - ele E a IA que ja vem pronta,
sem exigir contratar servico pago.

Usa regras/regex sobre linguagem natural em portugues (o idioma do time
que escreveu o spec) para propor testes. Nao inventa valores de negocio
(secao 9/14): quando reconhece um campo que "parece" representar estado
(status, situacao...) sem conseguir extrair um valor esperado explicito
do texto do usuario, ele NAO adivinha - apenas sinaliza como sugestao de
atencao.

Regras de negocio condicionais (ex: "Clientes PREMIUM devem estar ativos
e ter limite maior que 1000."): a deteccao SO cria uma regra condicional
quando o valor mencionado ("PREMIUM") realmente aparece em algum campo de
algum item de um array na resposta real - nunca por adivinhacao. Isso e
o que a torna generica para qualquer API (nao e um dicionario de valores
de nenhum cliente especifico), ao mesmo tempo que cumpre "a IA deve
analisar o response real da API".
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from typing import Any

from app.ai.base import AIProvider
from app.core.error_messages import friendly_status_message
from app.engine.evaluator import MISSING, get_by_path, type_name
from app.engine.templating import find_placeholders

_TYPE_WORDS = {
    "numero": "number",
    "número": "number",
    "inteiro": "integer",
    "texto": "string",
    "string": "string",
    "booleano": "boolean",
    "bool": "boolean",
    "array": "array",
    "lista": "array",
    "objeto": "object",
}

_FILLER_PREFIXES = [
    r"^quero garantir que\s+",
    r"^quero validar que\s+",
    r"^quero que\s+",
    r"^preciso que\s+",
    r"^preciso garantir que\s+",
    r"^desejo que\s+",
    r"^valide que\s+",
    r"^verifique que\s+",
    r"^garanta que\s+",
    r"^\s*e que\s+",
    r"^que\s+",
    r"^devem\s+",
    r"^deve\s+",
    r"^precisam\s+",
    r"^precisa\s+",
    r"^t[eê]m\s+que\s+",
    r"^tem\s+que\s+",
    r"^ter\s+",
    r"^possuir\s+",
    r"^tenham\s+",
    r"^tenha\s+",
]

_FIELD_ARTICLES = [
    r"^o campo\s+",
    r"^a propriedade\s+",
    r"^campo\s+",
    r"^propriedade\s+",
    r"^o\s+",
    r"^a\s+",
]

# Sinonimos genericos PT -> possiveis nomes/tokens reais de campo em uma API.
# Nao e especifico de nenhum dominio/cliente - so vocabulario comum de APIs
# REST (contadores, estados booleanos, dados de contato, metricas sociais
# genericas como "curtidas"/"seguidores" que aparecem em qualquer API social,
# nao so na do GitHub). E usado como um dicionario PT->EN para expandir os
# tokens da frase do usuario antes de comparar com os tokens dos campos
# REAIS observados na resposta (ver _score_fields) - nunca decide um campo
# sozinho, so amplia o que pode "bater" com o que existe de verdade.
_SYNONYMS: dict[str, list[str]] = {
    "ativo": ["active", "is_active", "enabled"],
    "ativos": ["active", "is_active", "enabled"],
    "ativa": ["active", "is_active", "enabled"],
    "ativas": ["active", "is_active", "enabled"],
    "inativo": ["active", "is_active", "enabled"],
    "inativos": ["active", "is_active", "enabled"],
    "inativa": ["active", "is_active", "enabled"],
    "inativas": ["active", "is_active", "enabled"],
    "habilitado": ["enabled", "active", "is_active"],
    "habilitados": ["enabled", "active", "is_active"],
    "habilitada": ["enabled", "active", "is_active"],
    "habilitadas": ["enabled", "active", "is_active"],
    "desabilitado": ["enabled", "active", "is_active"],
    "desabilitados": ["enabled", "active", "is_active"],
    "privado": ["private"],
    "privada": ["private"],
    "privados": ["private"],
    "privadas": ["private"],
    "publico": ["public", "visibility"],
    "publica": ["public", "visibility"],
    "publicos": ["public", "visibility"],
    "publicas": ["public", "visibility"],
    # "nome" NAO inclui "full_name": sao conceitos diferentes ("nome" vs
    # "nome completo") e um so deve puxar o outro quando "completo" tambem
    # aparecer na frase - ver "completo"/_score_fields para o desempate.
    "nome": ["name"],
    "completo": ["full"],
    "completa": ["full"],
    "completos": ["full"],
    "completas": ["full"],
    "limite": ["limit", "credit_limit", "max_limit", "cap"],
    "preco": ["price", "amount", "value", "cost"],
    "preço": ["price", "amount", "value", "cost"],
    "valor": ["value", "amount", "price"],
    "quantidade": ["quantity", "amount", "count", "qty", "total"],
    "numero": ["number", "num", "count", "total"],
    "número": ["number", "num", "count", "total"],
    "idade": ["age"],
    "telefone": ["phone", "telephone", "phone_number", "mobile"],
    "endereco": ["address"],
    "endereço": ["address"],
    "email": ["email", "mail"],
    "status": ["status", "state"],
    "situacao": ["status", "state", "situation"],
    "situação": ["status", "state", "situation"],
    "tipo": ["type", "tier", "category", "kind"],
    "categoria": ["category", "type", "tier"],
    "estado": ["state", "status"],
    "estrela": ["star", "stars", "stargazers", "stargazers_count"],
    "estrelas": ["star", "stars", "stargazers", "stargazers_count"],
    "garfo": ["fork", "forks", "forks_count"],
    "garfos": ["fork", "forks", "forks_count"],
    "observador": ["watcher", "watchers", "watchers_count"],
    "observadores": ["watcher", "watchers", "watchers_count"],
    "seguidor": ["follower", "followers"],
    "seguidores": ["follower", "followers"],
    "curtida": ["like", "likes"],
    "curtidas": ["like", "likes"],
    "visualizacao": ["view", "views"],
    "visualizacoes": ["view", "views"],
    "visualização": ["view", "views"],
    "visualizações": ["view", "views"],
    "descricao": ["description", "desc"],
    "descrição": ["description", "desc"],
    "proprietario": ["owner"],
    "proprietário": ["owner"],
    "dono": ["owner"],
    "linguagem": ["language", "lang"],
    "licenca": ["license"],
    "licença": ["license"],
    "criado": ["created", "created_at"],
    "criacao": ["created", "created_at"],
    "criação": ["created", "created_at"],
    "atualizado": ["updated", "updated_at"],
    "atualizacao": ["updated", "updated_at"],
    "atualização": ["updated", "updated_at"],
    "avaliacao": ["rating", "score"],
    "avaliação": ["rating", "score"],
    "nota": ["rating", "score"],
    "estoque": ["stock", "inventory"],
    "saldo": ["balance"],
    "desconto": ["discount"],
}

_ADJECTIVE_BOOL_MAP: dict[str, bool] = {
    # Cada adjetivo e afirmativo do SEU PROPRIO conceito resolvido (ex:
    # "publico" == True quando o campo encontrado for algo como "public"/
    # "visibility"="public"). Negacao ("nao seja X") e tratada a parte pelo
    # operador (not_equals) - NAO e o mesmo que "privado"/"publico" serem
    # polaridades opostas do MESMO campo, porque muitas vezes representam
    # campos REAIS diferentes (ex: booleano "private" vs enum "visibility").
    "ativo": True,
    "ativos": True,
    "ativa": True,
    "ativas": True,
    "inativo": False,
    "inativos": False,
    "inativa": False,
    "inativas": False,
    "habilitado": True,
    "habilitados": True,
    "habilitada": True,
    "habilitadas": True,
    "desabilitado": False,
    "desabilitados": False,
    "desabilitada": False,
    "desabilitadas": False,
    "disponivel": True,
    "disponiveis": True,
    "indisponivel": False,
    "indisponiveis": False,
    "valido": True,
    "validos": True,
    "invalido": False,
    "invalidos": False,
    "privado": True,
    "privada": True,
    "privados": True,
    "privadas": True,
    "publico": True,
    "publica": True,
    "publicos": True,
    "publicas": True,
}

# "publico"/"privado" quase sempre descrevem o MESMO conceito por campos
# REAIS diferentes (ex: booleano "private", ou booleano "public", ou enum
# "visibility") - ver _SYNONYMS acima, onde cada um so aponta pro seu
# proprio alvo. Quando o alvo direto nao existe na resposta, tentamos o
# antonimo: "for publico" tambem pode resolver via um campo "private" real,
# soh que com o valor NEGADO (publico == nao-privado). So existe para este
# par (nao eh um mecanismo generico de antonimos, so cobre o caso concreto
# de visibilidade que aparece em varias APIs reais).
_ADJECTIVE_ANTONYMS: dict[str, str] = {
    "publico": "privado",
    "publica": "privado",
    "publicos": "privado",
    "publicas": "privado",
    "privado": "publico",
    "privada": "publico",
    "privados": "publico",
    "privadas": "publico",
}

# Numerais por extenso mais comuns em frases de teste ("maior que zero"...).
# Nao e um dicionario de dominio - so numeros cardinais basicos em portugues.
_PT_NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "três": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
}

_STOPWORDS = {
    "o", "a", "os", "as", "de", "do", "da", "dos", "das", "um", "uma", "uns", "umas",
    "que", "e", "no", "na", "nos", "nas", "seu", "sua", "seus", "suas", "para", "com",
    # pronomes/palavras genericas: nunca sao, por si so, um nome de campo -
    # sem isso, "ele esteja ativo" tentava resolver "ele" (3 letras) contra
    # QUALQUER campo que por coincidencia contivesse essas letras em
    # sequencia (bug real: "ele" batia em "rel-EAS-es_url" via substring).
    "ele", "ela", "eles", "elas", "isso", "isto", "aquilo", "dele", "dela",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _strip_prefixes(text: str, patterns: list[str]) -> str:
    changed = True
    while changed:
        changed = False
        for pat in patterns:
            new_text = re.sub(pat, "", text, flags=re.IGNORECASE)
            if new_text != text:
                text = new_text
                changed = True
    return text.strip()


def _clean_value(raw: str) -> str | int | float | bool:
    v = raw.strip().strip(".").strip(",").strip()
    if v.startswith('"') and v.endswith('"'):
        v = v[1:-1]
    if v.startswith("'") and v.endswith("'"):
        v = v[1:-1]
    low = v.lower()
    if low in ("verdadeiro", "true"):
        return True
    if low in ("falso", "false"):
        return False
    number_word = _PT_NUMBER_WORDS.get(_strip_accents(low))
    if number_word is not None:
        return number_word
    try:
        if re.fullmatch(r"-?\d+", v):
            return int(v)
        if re.fullmatch(r"-?\d+\.\d+", v):
            return float(v)
    except ValueError:
        pass
    return v


def _map_field_name(field_raw: str) -> str:
    field = _strip_prefixes(field_raw.strip(), _FIELD_ARTICLES)
    low = field.lower()
    if re.search(r"tempo de resposta|response time|latencia|lat[eê]ncia", low):
        return "$.response_time_ms"
    if re.search(r"c[oó]digo (de status|http)|status code|http status", low):
        return "$.status_code"
    return field


_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9À-ÿ]+")


def _tokenize(name: str) -> list[str]:
    """Quebra um nome de campo (snake_case, camelCase, dot.path, frase em
    portugues...) em tokens normalizados (minusculo, sem acento). Usado dos
    dois lados da comparacao (o que o usuario escreveu x os campos reais da
    resposta) para que a comparacao nao dependa de convencao de nome."""
    spaced = _CAMEL_BOUNDARY_RE.sub(" ", name)
    spaced = _NON_ALNUM_RE.sub(" ", spaced)
    return [_strip_accents(t.lower()) for t in spaced.split() if t]


def _expand_tokens(tokens: list[str]) -> set[str]:
    expanded = set(tokens)
    for t in tokens:
        for syn in _SYNONYMS.get(t, []):
            expanded.update(_tokenize(syn))
    return expanded


def _score_fields(candidate: str, known_fields: list[str]) -> list[tuple[str, float]]:
    """Pontua cada campo real pela sobreposicao de tokens com o candidato
    (apos expandir por sinonimos). Puramente mecanico/generico - a
    pontuacao vem de quanto do TEXTO REAL do campo bate com o que foi
    escrito, nunca de uma lista fixa de campos de um cliente.

    Entre dois campos com a MESMA sobreposicao (ex: "name" e "full_name"
    ambos batendo em "nome"), o campo com MENOS tokens "extras" (nao
    mencionados pelo usuario) e mais preciso e vence no desempate - e assim
    que "nome do repositorio" -> name (nao full_name, que so deveria vencer
    se o usuario disser "nome COMPLETO"). Sem fallback de substring bruta:
    ele causava falso-positivo real (candidato curto tipo "ele" batendo por
    coincidencia de letras dentro de um campo nao relacionado, ex.
    "releases_url") - a correspondencia so conta via token inteiro (exato,
    sinonimo, ou camelCase/snake_case), nunca por pedaco de string."""
    cand_tokens = [t for t in _tokenize(candidate) if t not in _STOPWORDS and len(t) > 1]
    if not cand_tokens:
        return []
    expanded = _expand_tokens(cand_tokens)

    scored: list[tuple[str, float]] = []
    for f in known_fields:
        f_tokens = set(_tokenize(f))
        overlap = len(f_tokens & expanded)
        if overlap == 0:
            continue
        extra = len(f_tokens - expanded)
        scored.append((f, overlap - 0.1 * extra))
    scored.sort(key=lambda pair: -pair[1])
    return scored


def _resolve_field(candidate: str, known_fields: list[str]) -> str | None:
    """Tenta mapear uma palavra/frase em portugues para um nome de campo
    REAL observado na resposta (known_fields).

    REGRA FUNDAMENTAL: quando `known_fields` esta disponivel (ja existe uma
    resposta real testada) e nao ha uma correspondencia confiavel, retorna
    None - o chamador NAO deve inventar um nome de campo que nao existe na
    resposta (o candidato original nunca vira o campo "por padrao"). So
    quando ainda nao ha nenhuma resposta real para conferir (known_fields
    vazio) e que mantemos o palpite antigo, para o fluxo continuar
    funcionando antes do primeiro "Testar API".
    """
    if not known_fields:
        norm_candidate = _strip_accents(candidate.strip().lower())
        syns = _SYNONYMS.get(norm_candidate)
        if syns:
            return syns[0]
        return candidate

    norm_candidate_full = _strip_accents(candidate.strip().lower())
    for f in known_fields:
        if _strip_accents(f.lower()) == norm_candidate_full:
            return f

    scored = _score_fields(candidate, known_fields)
    if not scored:
        return None
    if len(scored) == 1 or scored[0][1] > scored[1][1]:
        return scored[0][0]
    return None  # empate entre campos diferentes - nao decide sozinho


def _resolve_bool_field(
    adj_norm: str, want_positive: bool, known_fields: list[str], sample_source: dict | list | None = None
) -> tuple[str, bool] | None:
    """Resolve um adjetivo de estado booleano (ex: 'ativo', 'publico') para
    um campo REAL booleano por nome, tentando primeiro o alvo direto e, se
    nao existir/nao for booleano, o antonimo com o valor negado (ex:
    'publico' -> campo 'private' real, expected=False).

    So aceita um candidato se o VALOR observado nele realmente for
    booleano - isso evita o caso em que o nome bate (ex: 'publico' ->
    sinonimo 'visibility') mas o campo de verdade guarda uma STRING
    ('visibility': 'public'), que deve ser tratada por
    _resolve_adjective_via_value, nao virar True/False as cegas. Nunca
    inventa: so retorna algo se um campo booleano de verdade existir."""
    sample = sample_source[0] if isinstance(sample_source, list) and sample_source else sample_source

    for candidate_word, negate in ((adj_norm, False), (_ADJECTIVE_ANTONYMS.get(adj_norm), True)):
        if not candidate_word:
            continue
        field = _resolve_field(candidate_word, known_fields)
        if field is None:
            continue
        observed = get_by_path(sample, field) if isinstance(sample, dict) else MISSING
        if sample is None or observed is MISSING or isinstance(observed, bool):
            expected = (not want_positive) if negate else want_positive
            return field, expected

    return None


def _suggest_similar_fields(candidate: str, known_fields: list[str], limit: int = 4) -> list[str]:
    """Lista campos plausiveis (mesmo com pontuacao empatada/baixa) para
    ajudar o usuario quando a IA nao conseguiu decidir sozinha - usado na
    mensagem de esclarecimento, nunca para criar uma regra sozinha."""
    scored = _score_fields(candidate, known_fields)
    return [f for f, _ in scored[:limit]]


def _clarification_message(candidate: str, known_fields: list[str]) -> str:
    suggestions = _suggest_similar_fields(candidate, known_fields)
    msg = f'Não consegui identificar com segurança qual campo da resposta corresponde a "{candidate}".'
    if suggestions:
        msg += f" Campos parecidos encontrados: {', '.join(suggestions)}."
    elif known_fields:
        msg += f" Campos disponíveis: {', '.join(known_fields[:15])}."
    return msg


def _try_adjective_as_field(
    operator: str, m: re.Match, known_fields: list[str], sample_source: dict | list | None = None
) -> dict | None:
    """Segunda tentativa quando o "campo" extraido pelo padrao normal
    (sujeito da frase, ex: "repositorio") nao bate com nada real: verifica
    se o texto capturado como VALOR (ex: "privado" em "nao seja privado")
    e, na verdade, um adjetivo de estado conhecido - nesse caso ELE, e nao
    o sujeito, e que deve virar o campo (via o mesmo resolvedor generico,
    que continua podendo devolver None se tambem nao achar nada real)."""
    if operator not in ("equals", "not_equals"):
        return None
    try:
        value_raw = m.group("value")
    except (IndexError, re.error):
        return None
    if not value_raw:
        return None
    adj_norm = _strip_accents(value_raw.strip().rstrip(".").lower())
    if adj_norm not in _ADJECTIVE_BOOL_MAP:
        return None
    base_bool = _ADJECTIVE_BOOL_MAP[adj_norm]
    want_positive = (not base_bool) if operator == "not_equals" else base_bool

    # Campo booleano de verdade (direto ou antonimo) tem prioridade - so cai
    # para o valor observado (_resolve_adjective_via_value) quando nao existe
    # nenhum campo booleano correspondente (ver _resolve_bool_field: ele
    # mesmo ja rejeita um "match" cujo valor observado nao seja booleano,
    # entao a ordem aqui nao reintroduz o bug de atribuir True/False a um
    # campo que na verdade guarda uma string).
    bool_match = _resolve_bool_field(adj_norm, want_positive, known_fields, sample_source)
    if bool_match is not None:
        rfield, rexpected = bool_match
        return {"field": rfield, "operator": "equals", "expected": rexpected}

    value_match = _resolve_adjective_via_value(adj_norm, want_positive, sample_source)
    if value_match is not None:
        vfield, vvalue = value_match
        return {"field": vfield, "operator": "equals", "expected": vvalue}

    return {"unresolved": True, "candidate": adj_norm}


def _flatten_field_paths(obj: Any, prefix: str = "", depth: int = 0, out: list[str] | None = None) -> list[str]:
    if out is None:
        out = []
    if depth > 2 or len(out) > 80:
        return out
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            out.append(path)
            _flatten_field_paths(value, path, depth + 1, out)
    elif isinstance(obj, list) and obj:
        _flatten_field_paths(obj[0], f"{prefix}.0" if prefix else "0", depth + 1, out)
    return out


def _find_object_arrays(
    obj: Any, prefix: str = "", depth: int = 0, out: list | None = None
) -> list[tuple[str, list]]:
    """Encontra toda lista-de-objetos na resposta (ate profundidade 3),
    retornando [(caminho, lista)]. `prefix == ""` significa que a propria
    raiz da resposta e a lista."""
    if out is None:
        out = []
    if depth > 3:
        return out
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict):
            out.append((prefix, obj))
        return out
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, list) and value and isinstance(value[0], dict):
                out.append((path, value))
            elif isinstance(value, dict):
                _find_object_arrays(value, path, depth + 1, out)
    return out


def _detect_array_condition(text: str, response_ctx: dict | None) -> dict | None:
    """So retorna uma condicao se o valor mencionado no texto realmente
    aparece em algum campo de algum item de um array na resposta real -
    e assim que a deteccao fica ancorada nos dados observados, em vez de
    adivinhar (secao: 'a IA deve analisar o response real da API')."""
    if not response_ctx or not response_ctx.get("json_valid"):
        return None
    body = response_ctx.get("body_json")
    if body is None:
        return None
    arrays = _find_object_arrays(body)
    if not arrays:
        return None

    tokens: set[str] = set(re.findall(r"\b[A-ZÀ-Ú]{3,}\b", text))
    for a, b in re.findall(r'"([^"]+)"|\'([^\']+)\'', text):
        tokens.add(a or b)
    if not tokens:
        return None

    for array_path, items in arrays:
        sample_keys = sorted({k for item in items if isinstance(item, dict) for k in item})
        for key in sample_keys:
            values = {str(item.get(key)) for item in items if isinstance(item, dict) and item.get(key) is not None}
            for token in tokens:
                if token in values:
                    return {
                        "array_path": array_path,
                        "condition_field": key,
                        "condition_value": token,
                        "sample_keys": sample_keys,
                        "items": items,
                    }
    return None


def _resolve_adjective_via_value(
    adj_norm: str, want_positive: bool, sample_source: dict | list | None
) -> tuple[str, Any] | None:
    """Segundo mecanismo de ancoragem para adjetivos de estado (ex: 'ativo'):
    quando NAO existe um campo booleano dedicado (ex: 'active'), procura um
    campo cujo VALOR REAL observado corresponda ao conceito do adjetivo (ex:
    campo 'status' com valor 'ACTIVE') - exatamente o exemplo "o cliente
    esteja ativo" + {"status": "ACTIVE"} -> status == "ACTIVE". So retorna
    um valor que REALMENTE apareceu na resposta - nunca inventa um valor
    (para o caso negativo, so devolve outro valor que o mesmo campo tambem
    assumiu de verdade em algum item, nunca uma string inventada)."""
    if sample_source is None:
        return None
    items = sample_source if isinstance(sample_source, list) else [sample_source]
    expanded = _expand_tokens([adj_norm])

    field_values: dict[str, set[str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            if isinstance(value, str) and value:
                field_values.setdefault(key, set()).add(value)

    for field, values in field_values.items():
        for value in values:
            if _strip_accents(value.lower()) not in expanded:
                continue
            if want_positive:
                return field, value
            others = [v for v in values if _strip_accents(v.lower()) not in expanded]
            if others:
                return field, others[0]
            return None
    return None


def _extract_consequent(text: str, condition_value: str) -> str:
    idx = text.upper().find(condition_value.upper())
    if idx == -1:
        return text
    after = text[idx + len(condition_value) :]
    after = re.sub(r"^[\s,]*", "", after)
    return after


# "Se o repositorio for publico, quero garantir que tenha mais de 100
# estrelas." - regra condicional sobre uma resposta PLANA (nao uma lista de
# itens, como no caso de "clientes PREMIUM" acima). A condicao e a
# consequencia sao extraidas aqui; a RESOLUCAO de cada uma para um campo
# real reaproveita _parse_clause (o mesmo caminho usado por qualquer regra
# simples) - nunca um mecanismo separado de interpretacao.
_FLAT_CONDITION_RE = re.compile(r"^se\s+(?P<condition>.+?)\s*,\s*(?P<consequent>.+)$", re.IGNORECASE)


def _split_flat_condition(text: str) -> tuple[str, str] | None:
    m = _FLAT_CONDITION_RE.match(text.strip())
    if not m:
        return None
    return m.group("condition").strip(), m.group("consequent").strip()


# "o repositorio TENHA pelo menos 10 forks" - o sujeito ("o repositorio")
# antes do verbo nao e o campo (o campo real vem DEPOIS do numero, "forks");
# descartamos tudo antes do verbo para cair no mesmo padrao valor-primeiro
# de "pelo menos"/"no minimo"/"mais de"/"menos de"/"N ou mais" ja existente
# (evita duplicar um padrao por combinacao de sujeito+verbo+quantificador).
_QUANTITY_VERB_RE = re.compile(
    r"\b(?:tenha|tenham|possua|possuam)\s+(?=(?:pelo\s+menos|no\s+m[ií]nimo|mais\s+de|menos\s+de|\d+\s+ou\s+mais))",
    re.IGNORECASE,
)


def _strip_subject_before_quantity_verb(clause: str) -> str:
    m = _QUANTITY_VERB_RE.search(clause)
    if m and m.start() > 0:
        return clause[m.end() :]
    return clause


_CLAUSE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("boolean_state", re.compile(r"^(estar|esteja|ser|seja|for|ficar|fique)\s+(?P<adj>\w+)$", re.IGNORECASE)),
    (
        "type_is",
        re.compile(
            r"^(?P<field>.+?)\s+seja\s+(um|uma)?\s*"
            r"(?P<type>numero|número|inteiro|texto|string|booleano|bool|array|lista|objeto)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "is_email_format",
        re.compile(r"^(?P<field>.+?)\s+seja\s+(um\s+)?e-?mail\s+v[aá]lido", re.IGNORECASE),
    ),
    (
        "not_exists",
        re.compile(r"^(?P<field>.+?)\s+n[aã]o\s+(exista|esteja presente|esteja preenchid[oa]s?)", re.IGNORECASE),
    ),
    (
        "exists",
        re.compile(
            r"^(?P<field>.+?)\s+(exista|esteja presente|esteja definido|esteja preenchid[oa]s?)", re.IGNORECASE
        ),
    ),
    ("contains", re.compile(r"^(?P<field>.+?)\s+cont(enha|em)\s+(?P<value>.+)$", re.IGNORECASE)),
    ("starts_with", re.compile(r"^(?P<field>.+?)\s+comece\s+com\s+(?P<value>.+)$", re.IGNORECASE)),
    ("ends_with", re.compile(r"^(?P<field>.+?)\s+termine\s+com\s+(?P<value>.+)$", re.IGNORECASE)),
    (
        "greater_than_or_equal",
        re.compile(r"^(?P<field>.+?)\s+(?:seja\s+)?maior\s+ou\s+igual\s+a\s+(?P<value>.+)$", re.IGNORECASE),
    ),
    (
        # "pelo menos 10 forks" / "no minimo 10 forks" - valor ANTES do
        # campo, equivalente a "maior ou igual a" (mesmo operador existente,
        # so outra forma de expressar a mesma coisa em portugues).
        "greater_than_or_equal",
        re.compile(r"^pelo\s+menos\s+(?P<value>\d+(?:[.,]\d+)?)\s+(?P<field>.+)$", re.IGNORECASE),
    ),
    (
        "greater_than_or_equal",
        re.compile(r"^no\s+m[ií]nimo\s+(?P<value>\d+(?:[.,]\d+)?)\s+(?P<field>.+)$", re.IGNORECASE),
    ),
    (
        # "10 ou mais forks"
        "greater_than_or_equal",
        re.compile(r"^(?P<value>\d+(?:[.,]\d+)?)\s+ou\s+mais\s+(?P<field>.+)$", re.IGNORECASE),
    ),
    (
        # variante campo-primeiro: "o numero de forks seja pelo menos 10" ou
        # "o repositorio tenha pelo menos 10 forks" com sujeito embutido
        # (em vez da forma sem sujeito "tenha pelo menos 10 forks", ja
        # coberta pelo padrao valor-primeiro acima).
        "greater_than_or_equal",
        re.compile(
            r"^(?P<field>.+?)\s+(?:seja|tenha)\s+pelo\s+menos\s+(?P<value>\d+(?:[.,]\d+)?)$", re.IGNORECASE
        ),
    ),
    (
        "greater_than_or_equal",
        re.compile(
            r"^(?P<field>.+?)\s+(?:seja|tenha)\s+no\s+m[ií]nimo\s+(?P<value>\d+(?:[.,]\d+)?)$", re.IGNORECASE
        ),
    ),
    (
        "greater_than_or_equal",
        re.compile(r"^(?P<field>.+?)\s+(?:seja|tenha)\s+(?P<value>\d+(?:[.,]\d+)?)\s+ou\s+mais$", re.IGNORECASE),
    ),
    (
        "less_than_or_equal",
        re.compile(r"^(?P<field>.+?)\s+(?:seja\s+)?menor\s+ou\s+igual\s+a\s+(?P<value>.+)$", re.IGNORECASE),
    ),
    (
        "greater_than",
        re.compile(r"^(?P<field>.+?)\s+(?:seja\s+)?maior\s+(que|do que)\s+(?P<value>.+)$", re.IGNORECASE),
    ),
    (
        "less_than",
        re.compile(r"^(?P<field>.+?)\s+(?:seja\s+)?menor\s+(que|do que)\s+(?P<value>.+)$", re.IGNORECASE),
    ),
    (
        # "mais de 100 estrelas" - construcao com o numero ANTES do campo,
        # diferente de "estrelas maior que 100". Mesmo operador
        # (greater_than), so uma ordem de palavras diferente na frase.
        "greater_than",
        re.compile(r"^mais\s+de\s+(?P<value>\d+(?:[.,]\d+)?)\s+(?P<field>.+)$", re.IGNORECASE),
    ),
    (
        "less_than",
        re.compile(r"^menos\s+de\s+(?P<value>\d+(?:[.,]\d+)?)\s+(?P<field>.+)$", re.IGNORECASE),
    ),
    (
        "not_equals",
        re.compile(
            r"^(?P<field>.+?)\s+"
            r"(seja\s+diferente\s+de|esteja\s+diferente\s+de|n[aã]o\s+seja|n[aã]o\s+esteja|n[aã]o\s+for)\s+"
            r"(?P<value>.+)$",
            re.IGNORECASE,
        ),
    ),
    (
        "matches_regex",
        re.compile(r"^(?P<field>.+?)\s+siga\s+o\s+padr[aã]o\s+(?P<value>.+)$", re.IGNORECASE),
    ),
    (
        # "for" cobre a construcao condicional "se X for Y" (ver
        # _split_flat_condition) - mesmo verbo "ser", forma usada apos "se".
        "equals",
        re.compile(r"^(?P<field>.+?)\s+(seja|esteja|for|deve\s+ser|igual\s+a)\s+(?P<value>.+)$", re.IGNORECASE),
    ),
]

_STATE_FIELD_HINT = re.compile(r"status|situa[cç][aã]o|estado", re.IGNORECASE)

# --- padroes de pergunta (consulta/analise - secao "IA responde perguntas") ---
_Q_FIELDS_INSIDE_RE = re.compile(
    r"quais\s+campos\s+(?:existem\s+)?(?:tem\s+)?dentro\s+d[eo]\s+(?P<field>[\wÀ-ú.\-]+)", re.IGNORECASE
)
_Q_TYPE_RE = re.compile(
    r"qual\s+(?:é|e)\s+o\s+tipo\s+d[eo]\s+(?:campo\s+|propriedade\s+)?(?P<field>[\wÀ-ú.\-]+)", re.IGNORECASE
)
_Q_VALUE_RE = re.compile(
    r"qual\s+(?:foi|é|e)\s+(?:o\s+)?(?:retorno|valor)\s+d[oe]\s+campo\s+(?P<field>[\wÀ-ú.\-]+)"
    r"|valor\s+d[oe]\s+campo\s+(?P<field2>[\wÀ-ú.\-]+)",
    re.IGNORECASE,
)
_Q_EXISTS_RE = re.compile(r"(?:existe|h[aá])\s+(?:o\s+)?campo\s+(?P<field>[\wÀ-ú.\-]+)", re.IGNORECASE)


class HeuristicAIProvider(AIProvider):
    name = "heuristic"

    def is_available(self) -> bool:
        return True

    def suggest_from_response(self, response_ctx: dict, discovered_checks: list[dict]) -> dict:
        body = response_ctx.get("body_json")
        suggestions: list[dict] = []
        notes: list[str] = []

        if isinstance(body, dict):
            for key, value in body.items():
                if isinstance(value, list):
                    suggestions.append(
                        _suggestion(
                            category="field",
                            field=key,
                            operator="type_is",
                            expected="array",
                            description=f"'{key}' é uma lista - sugestão: garantir que não venha vazia",
                        )
                    )
                    suggestions.append(
                        _suggestion(
                            category="field",
                            field=key,
                            operator="not_equals",
                            expected="[]",
                            description=f"'{key}' não deveria ser uma lista vazia (ajuste se vazio for válido)",
                        )
                    )
                if isinstance(key, str) and _STATE_FIELD_HINT.search(key) and isinstance(value, str):
                    notes.append(
                        f"O campo '{key}' parece representar um estado de negócio (valor observado: "
                        f"'{value}'). A IA não define automaticamente qual valor é o esperado - "
                        f"adicione uma regra manualmente ou descreva no assistente de linguagem natural."
                    )
                if key.lower() == "id":
                    suggestions.append(
                        _suggestion(
                            category="field",
                            field=key,
                            operator="greater_than",
                            expected=0,
                            description="'id' maior que 0 (sugestão - assume IDs positivos)",
                        )
                    )

        status = response_ctx.get("status_code")
        if status is not None:
            family = f"{status // 100}xx"
            notes.append(f"HTTP {status} ({family}) observado nesta chamada.")

        summary = " ".join(notes) if notes else "Resposta analisada sem observações adicionais."
        return {"summary": summary, "suggestions": suggestions}

    def suggest_negative_cases(self, request_def: dict) -> list[dict]:
        method = (request_def.get("method") or "GET").upper()
        url = request_def.get("url", "")
        is_mutating = method in ("POST", "PUT", "PATCH", "DELETE")
        has_auth = (request_def.get("auth") or {}).get("type", "none") != "none"
        has_path_id = bool(re.search(r"/\d+(/|$)", url)) or "{id}" in url

        cases: list[dict] = []
        if has_path_id:
            cases.append(
                _negative_case(
                    "ID inexistente deve retornar 404",
                    "Chamar o mesmo endpoint com um ID que não existe deveria responder 404.",
                    method,
                    expected_status=404,
                    is_mutating=is_mutating,
                )
            )
            cases.append(
                _negative_case(
                    "ID inválido deve retornar 400",
                    "Chamar o endpoint com um ID em formato inválido (ex: texto em vez de número) "
                    "deveria responder 400.",
                    method,
                    expected_status=400,
                    is_mutating=is_mutating,
                )
            )
        if has_auth:
            cases.append(
                _negative_case(
                    "Sem autenticação deve retornar 401",
                    "Remover o header/token de autenticação deveria resultar em 401.",
                    method,
                    expected_status=401,
                    is_mutating=is_mutating,
                )
            )
            cases.append(
                _negative_case(
                    "Token inválido deve retornar 401",
                    "Usar um token/API key inválido deveria resultar em 401.",
                    method,
                    expected_status=401,
                    is_mutating=is_mutating,
                )
            )
        if request_def.get("query_params"):
            cases.append(
                _negative_case(
                    "Parâmetro inválido deve retornar 400",
                    "Enviar um valor fora do esperado em um parâmetro de query deveria "
                    "resultar em erro de validação (400).",
                    method,
                    expected_status=400,
                    is_mutating=is_mutating,
                )
            )
        return cases

    def nl_to_rules(self, text: str, response_ctx: dict | None) -> dict:
        array_ctx = _detect_array_condition(text, response_ctx)
        if array_ctx:
            consequent_text = _extract_consequent(text, array_ctx["condition_value"])
            known_fields = array_ctx["sample_keys"]
            sample_source: dict | list | None = array_ctx["items"]
        else:
            has_body = response_ctx and response_ctx.get("json_valid")
            known_fields = _flatten_field_paths(response_ctx.get("body_json")) if has_body else []
            sample_source = response_ctx.get("body_json") if has_body else None
            consequent_text = text

            flat_split = _split_flat_condition(text) if has_body else None
            if flat_split:
                condition_text, consequent_candidate = flat_split
                condition_clause = _strip_prefixes(condition_text, _FILLER_PREFIXES)
                condition_parsed = self._parse_clause(condition_clause, known_fields, sample_source)
                if condition_parsed is not None and not condition_parsed.get("unresolved"):
                    # Regra condicional sobre uma resposta PLANA (nao uma
                    # lista) - reaproveita o MESMO evaluate_check de
                    # array_path (evaluator.py trata um dict como lista de
                    # 1 item), so muda de onde a condicao veio.
                    array_ctx = {
                        "array_path": "",
                        "condition_field": condition_parsed["field"],
                        "condition_operator": condition_parsed["operator"],
                        "condition_value": condition_parsed["expected"],
                        "sample_keys": known_fields,
                        "items": [response_ctx.get("body_json")],
                        "is_flat_condition": True,
                    }
                    consequent_text = consequent_candidate
                else:
                    # A condicao ("se X for Y") nao bateu com nenhum campo
                    # real com seguranca - NAO inventa e NAO tenta tratar a
                    # frase inteira como uma regra simples (isso perderia a
                    # condicao silenciosamente). Sinaliza e para por aqui.
                    candidate = condition_parsed["candidate"] if condition_parsed else condition_text
                    msg = f"(condição) {_clarification_message(candidate, known_fields)}"
                    return {"rules": [], "unparsed": [msg]}

        rules: list[dict] = []
        unparsed: list[str] = []

        clauses = re.split(r"\s*(?:,| e |;|\n)\s*", consequent_text.strip())
        for raw_clause in clauses:
            clause = raw_clause.strip().rstrip(".")
            if not clause:
                continue
            parsed = self._parse_clause(clause, known_fields, sample_source)
            if parsed is None:
                unparsed.append(raw_clause.strip())
                continue
            if parsed.get("unresolved"):
                unparsed.append(_clarification_message(parsed["candidate"], known_fields))
                continue
            rules.append(_build_rule(parsed, array_ctx, raw_clause.strip()))

        return {"rules": rules, "unparsed": unparsed}

    def _parse_clause(
        self, clause: str, known_fields: list[str], sample_source: dict | list | None = None
    ) -> dict | None:
        clause_wo_filler = _strip_prefixes(clause, _FILLER_PREFIXES)
        clause_wo_filler = _strip_subject_before_quantity_verb(clause_wo_filler)
        for operator, pattern in _CLAUSE_PATTERNS:
            m = pattern.match(clause_wo_filler)
            if not m:
                continue

            if operator == "boolean_state":
                adj_norm = _strip_accents(m.group("adj").lower())
                if adj_norm not in _ADJECTIVE_BOOL_MAP:
                    continue
                want_positive = _ADJECTIVE_BOOL_MAP[adj_norm]
                # Campo booleano real (direto ou antonimo) primeiro;
                # _resolve_bool_field ja rejeita um "match" por nome cujo
                # valor observado nao seja booleano (ex: 'visibility' com
                # valor string 'public'), entao so cai para
                # _resolve_adjective_via_value quando nao ha campo booleano
                # de verdade correspondente.
                bool_match = _resolve_bool_field(adj_norm, want_positive, known_fields, sample_source)
                if bool_match is not None:
                    rfield, rexpected = bool_match
                    return {"field": rfield, "operator": "equals", "expected": rexpected}
                value_match = _resolve_adjective_via_value(adj_norm, want_positive, sample_source)
                if value_match is not None:
                    vfield, vvalue = value_match
                    return {"field": vfield, "operator": "equals", "expected": vvalue}
                if known_fields:
                    return {"unresolved": True, "candidate": adj_norm}
                return {"field": adj_norm, "operator": "equals", "expected": want_positive}

            field_raw = m.group("field")
            field_candidate = _map_field_name(field_raw)
            if not field_candidate:
                continue

            if field_candidate.startswith("$."):
                field = field_candidate
            else:
                field = _resolve_field(field_candidate, known_fields)
                if field is None:
                    # O "campo" extraido da frase nao bateu com nada real na
                    # resposta. Antes de desistir, verifica se o que foi
                    # capturado como VALOR e na verdade um adjetivo de estado
                    # conhecido (ex: "o repositorio nao seja privado" -> o
                    # sujeito "repositorio" nao e um campo, mas "privado" e -
                    # nunca inventa: so tenta essa segunda leitura quando a
                    # primeira falhou em achar um campo real).
                    adj_retry = _try_adjective_as_field(operator, m, known_fields, sample_source)
                    if adj_retry is not None:
                        return adj_retry
                    return {"unresolved": True, "candidate": field_candidate}

            if operator == "type_is":
                expected = _TYPE_WORDS.get(m.group("type").lower(), m.group("type").lower())
            elif operator in ("exists", "not_exists", "is_email_format"):
                expected = None
            else:
                expected = _clean_value(m.group("value"))

            return {"field": field, "operator": operator, "expected": expected}

        return None

    def answer_question(self, question: str, response_ctx: dict) -> str:
        if not response_ctx or not response_ctx.get("json_valid"):
            return "Ainda não há uma resposta JSON válida para consultar. Clique em 'Testar API' primeiro."
        body = response_ctx.get("body_json")
        known_fields = _flatten_field_paths(body)

        m = _Q_FIELDS_INSIDE_RE.search(question)
        if m:
            candidate = m.group("field")
            field = _resolve_field(candidate, known_fields) or candidate
            value = get_by_path(body, field)
            if isinstance(value, dict):
                return f"Os campos dentro de '{field}' são: {', '.join(value.keys())}."
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return f"'{field}' é uma lista; cada item tem os campos: {', '.join(value[0].keys())}."
            if value is MISSING:
                return f"Não encontrei um campo chamado '{field}' na resposta."
            return f"'{field}' não é um objeto/lista de objetos (é {type_name(value)}), não há campos internos."

        m = _Q_TYPE_RE.search(question)
        if m:
            candidate = m.group("field")
            field = _resolve_field(candidate, known_fields) or candidate
            value = get_by_path(body, field)
            if value is MISSING:
                return f"Não encontrei o campo '{field}' na resposta."
            return f"O campo '{field}' é do tipo {type_name(value)} (valor observado: {value!r})."

        m = _Q_VALUE_RE.search(question)
        if m:
            candidate = m.group("field") or m.group("field2")
            field = _resolve_field(candidate, known_fields) or candidate
            value = get_by_path(body, field)
            if value is MISSING:
                preview = ", ".join(known_fields[:20])
                return f"Não encontrei o campo '{field}' na resposta. Campos disponíveis: {preview}"
            return f"O campo '{field}' retornou: {value!r}."

        m = _Q_EXISTS_RE.search(question)
        if m:
            candidate = m.group("field")
            field = _resolve_field(candidate, known_fields) or candidate
            value = get_by_path(body, field)
            exists = value is not MISSING
            estado = "existe" if exists else "não existe"
            return f"{'Sim' if exists else 'Não'}, o campo '{field}' {estado} nesta resposta."

        for word in re.findall(r"[\wÀ-ú_]{3,}", question):
            field = _resolve_field(word, known_fields)
            if field in known_fields:
                value = get_by_path(body, field)
                return f"'{field}': {value!r} (tipo {type_name(value)})."

        preview = ", ".join(known_fields[:25])
        return (
            "Não entendi exatamente o que você quer saber. Tente perguntar, por exemplo: "
            '"qual o valor do campo X", "qual o tipo de X" ou "quais campos existem dentro de X". '
            f"Campos disponíveis nesta resposta: {preview}"
        )

    def suggest_scenarios(self, check: dict) -> list[dict]:
        return _build_scenarios(check.get("field", "campo"), check.get("operator", ""), check.get("expected"))

    def chat(self, message: str, context: dict) -> str:
        return _heuristic_chat(message, context)

    def suggest_test_data(self, variables: list[str], response_ctx: dict | None, count: int) -> dict:
        return _build_test_data(variables, count)

    def explain_failure(self, result: dict, response_ctx: dict | None) -> str:
        field = result.get("field") or "(verificação global)"
        expected = result.get("expected")
        actual = result.get("actual")
        status = (response_ctx or {}).get("status_code")
        category = result.get("category", "field")

        lines = []
        if status is not None:
            lines.append(
                f"A API respondeu HTTP {status}, mas a verificação em '{field}' não correspondeu "
                f"à expectativa configurada."
            )
        else:
            lines.append(f"A verificação em '{field}' não correspondeu à expectativa configurada.")
        lines.append(f"Expected: {expected}")
        lines.append(f"Actual: {actual}")
        lines.append("")
        lines.append("Possíveis próximos passos:")
        if category == "http":
            lines.append("- verificar se o endpoint/ambiente usado está correto;")
            lines.append("- verificar se a API está no ar e respondendo como esperado;")
        elif category == "performance":
            lines.append("- verificar carga do ambiente de teste no momento da execução;")
            lines.append("- considerar se o limite configurado é realista para este endpoint;")
        else:
            lines.append("- verificar a regra de negócio associada a este campo;")
            lines.append("- verificar o estado/massa de dados usada no ambiente de teste;")
            lines.append("- confirmar se a expectativa configurada ainda reflete o contrato atual da API;")
        return "\n".join(lines)


def _build_rule(parsed: dict, array_ctx: dict | None, raw_text: str) -> dict:
    field = parsed["field"]
    operator = parsed["operator"]
    expected = parsed["expected"]

    if array_ctx:
        condition_operator = array_ctx.get("condition_operator", "equals")
        rule_part = f"{field} {operator} {expected if expected is not None else ''}".strip()
        if array_ctx.get("is_flat_condition"):
            description = (
                f"Se {array_ctx['condition_field']} {condition_operator} "
                f"\"{array_ctx['condition_value']}\": {rule_part}"
            )
        else:
            where = f"{array_ctx['condition_field']} {condition_operator} \"{array_ctx['condition_value']}\""
            description = f"Para itens de '{array_ctx['array_path'] or '(lista raiz)'}' onde {where}: {rule_part}"
        return {
            "id": str(uuid.uuid4()),
            "source": "ai_suggested",
            "category": "field",
            "field": field,
            "operator": operator,
            "expected": expected,
            "array_path": array_ctx["array_path"],
            "condition_field": array_ctx["condition_field"],
            "condition_operator": condition_operator,
            "condition_expected": array_ctx["condition_value"],
            "description": description,
            "confidence": 0.75,
            "raw_text": raw_text,
        }

    return {
        "id": str(uuid.uuid4()),
        "source": "ai_suggested",
        "category": "http" if field.startswith("$.") else "field",
        "field": field,
        "operator": operator,
        "expected": expected,
        "description": f"{field} {operator} {expected if expected is not None else ''}".strip(),
        "confidence": 0.85,
        "raw_text": raw_text,
    }


def _suggestion(category: str, field: str, operator: str, expected, description: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "source": "ai_suggested",
        "category": category,
        "field": field,
        "operator": operator,
        "expected": expected,
        "description": description,
    }


def _negative_case(title: str, description: str, method: str, expected_status: int, is_mutating: bool) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "method": method,
        "expected_status": expected_status,
        "is_mutating": is_mutating,
        "requires_confirmation": is_mutating,
        "safe_to_auto_run": not is_mutating,
    }


def _build_scenarios(field: str, operator: str, expected: Any) -> list[dict]:
    """Funcao 3 ("Sugerir cenarios"): a partir de UMA regra ja estruturada
    (nao de texto livre), propoe 2-3 valores de exemplo com o resultado
    esperado (PASS/FAIL). Puramente derivado do operador/valor - nao
    depende de nenhum campo especifico, funciona para qualquer regra."""

    def scenario(value: Any, outcome: str, note: str = "") -> dict:
        desc = f"{field} = {value!r} → {outcome}"
        if note:
            desc += f" ({note})"
        return {"value": value, "expected_outcome": outcome, "description": desc}

    if operator in ("greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal"):
        try:
            e = float(expected)
        except (TypeError, ValueError):
            return []
        is_int = isinstance(expected, int) or (
            isinstance(expected, str) and re.fullmatch(r"-?\d+", expected.strip())
        )

        def fmt(v: float) -> Any:
            return int(round(v)) if is_int else round(v, 2)

        delta_big = max(abs(e) * 0.2, 1)
        if operator == "greater_than":
            return [
                scenario(fmt(e + delta_big), "PASS", "acima do limite"),
                scenario(fmt(e), "FAIL", "igual ao limite não é suficiente"),
                scenario(fmt(e - 1), "FAIL", "abaixo do limite"),
            ]
        if operator == "greater_than_or_equal":
            return [
                scenario(fmt(e + delta_big), "PASS", "acima do limite"),
                scenario(fmt(e), "PASS", "igual ao limite já é suficiente"),
                scenario(fmt(e - 1), "FAIL", "abaixo do limite"),
            ]
        if operator == "less_than":
            return [
                scenario(fmt(e - delta_big), "PASS", "abaixo do limite"),
                scenario(fmt(e), "FAIL", "igual ao limite não é suficiente"),
                scenario(fmt(e + 1), "FAIL", "acima do limite"),
            ]
        return [  # less_than_or_equal
            scenario(fmt(e - delta_big), "PASS", "abaixo do limite"),
            scenario(fmt(e), "PASS", "igual ao limite já é suficiente"),
            scenario(fmt(e + 1), "FAIL", "acima do limite"),
        ]

    if operator == "equals":
        if isinstance(expected, bool) or str(expected).strip().lower() in ("true", "false"):
            exp_bool = expected if isinstance(expected, bool) else str(expected).strip().lower() == "true"
            return [scenario(exp_bool, "PASS"), scenario(not exp_bool, "FAIL")]
        return [scenario(expected, "PASS"), scenario(f"(qualquer valor diferente de {expected!r})", "FAIL")]

    if operator == "not_equals":
        return [scenario(f"(qualquer valor diferente de {expected!r})", "PASS"), scenario(expected, "FAIL")]

    return []


_CHAT_HTTP_STATUS_RE = re.compile(r"\b([1-5]\d{2})\b")
# "explic" cobre "explicar"/"explicando"; "expliqu" cobre "explique"/"expliquei"
# (troca ortografica c->qu do portugues antes de e/i) - sem as duas formas,
# "Explique esse erro 401" (bem comum) nao batia com o padrao.
_CHAT_EXPLAIN_RE = re.compile(r"explic|expliqu|o que|por ?que|descrev|resum", re.IGNORECASE)
_CHAT_COUNT_RE = re.compile(r"\b(\d+)\b")
_NO_CONTEXT = "Não tenho essa informação no contexto atual."


def _chat_has(norm_message: str, *words: str) -> bool:
    return any(w in norm_message for w in words)


def _chat_describe_request(context: dict) -> str:
    method, url = context.get("method"), context.get("url")
    if not method and not url:
        return _NO_CONTEXT
    parts = [f"Request: {method} {url}."]
    body = context.get("request_body")
    parts.append(f"Body enviado: {body[:400]}" if body else "Sem body no request.")
    headers = context.get("request_headers") or {}
    if headers:
        parts.append(f"Headers enviados: {', '.join(headers.keys())}.")
    auth_type = context.get("auth_type")
    if auth_type and auth_type != "none":
        parts.append(f"Usa autenticação do tipo '{auth_type}'.")
    elif auth_type == "none":
        parts.append("Sem autenticação configurada.")
    return " ".join(parts)


def _chat_describe_response(context: dict) -> str:
    status, body = context.get("status_code"), context.get("body_json")
    error = context.get("error")
    if error:
        return f"A chamada não obteve resposta: {error}"
    if status is None and body is None:
        return _NO_CONTEXT
    parts = [f"Response: HTTP {status}." if status is not None else "Ainda sem status HTTP observado."]
    if context.get("json_valid") is False:
        parts.append("O corpo não é um JSON válido.")
    elif isinstance(body, dict) and body:
        parts.append(f"Campos: {_chat_field_summary(body)}.")
    elif isinstance(body, list):
        parts.append(f"É uma lista com {len(body)} item(ns).")
    return " ".join(parts)


def _chat_field_summary(body: Any, limit: int = 20) -> str:
    if isinstance(body, dict) and body:
        items = list(body.items())[:limit]
        return ", ".join(f"{k} ({type_name(v)})" for k, v in items)
    if isinstance(body, list) and body and isinstance(body[0], dict):
        items = list(body[0].items())[:limit]
        return "lista de objetos, cada um com: " + ", ".join(f"{k} ({type_name(v)})" for k, v in items)
    return ""


def _chat_request_field_names(context: dict) -> list[str]:
    """Nomes de campo/variavel para basear uma massa gerada pelo chat -
    tenta as chaves do JSON do body enviado (ex: title/price/stock) e,
    se nao houver, placeholders `{{var}}` no body/URL (ver app.engine.
    templating). Nunca inventa um nome que nao apareça em um dos dois."""
    request_body = context.get("request_body")
    if isinstance(request_body, str) and request_body.strip():
        try:
            parsed = json.loads(request_body)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict) and parsed:
            return list(parsed.keys())
        placeholders = find_placeholders(request_body)
        if placeholders:
            return sorted(placeholders)
    placeholders = find_placeholders(context.get("url") or "")
    return sorted(placeholders) if placeholders else []


def _chat_fields_mentioned(message: str, known_fields: list[str]) -> list[str]:
    norm = _strip_accents(message.lower())
    mentioned = []
    for f in known_fields:
        base = _strip_accents(f.split(".")[-1].lower())
        if base and re.search(rf"\b{re.escape(base)}\b", norm):
            mentioned.append(f)
    return mentioned


def _chat_suggest_rule_for_field(field: str, body: Any) -> str:
    value = get_by_path(body, field)
    base = field.split(".")[-1].lower()
    if value is MISSING:
        return f"{field} exists"
    if isinstance(value, bool):
        return f"{field} equals {value}"
    if isinstance(value, int | float):
        if re.search(r"stock|qty|quantidade|count|total|estoque", base):
            return f"{field} greater_than_or_equal 0"
        return f"{field} greater_than 0"
    if isinstance(value, str):
        return f"{field} exists"
    return f"{field} exists"


def _chat_scenarios_for_rules(message: str, rules: list[dict], norm: str) -> str:
    if not rules:
        return (
            f"{_NO_CONTEXT} Não há nenhuma regra aprovada ainda para eu basear cenários — adicione uma regra "
            "primeiro (manualmente ou via Assistente de IA)."
        )
    mentioned = _chat_fields_mentioned(message, [r.get("field") or "" for r in rules])
    target_rules = [r for r in rules if r.get("field") in mentioned] or rules[:1]

    wants_positive = _chat_has(norm, "positiv")
    wants_negative = _chat_has(norm, "negativ")
    wants_boundary = _chat_has(norm, "borda", "limite", "fronteira")

    lines = []
    for rule in target_rules:
        scenarios = _build_scenarios(rule.get("field", "campo"), rule.get("operator", ""), rule.get("expected"))
        if not scenarios:
            continue
        for s in scenarios:
            if wants_positive and s["expected_outcome"] != "PASS":
                continue
            if wants_negative and s["expected_outcome"] != "FAIL":
                continue
            lines.append(f"- {s['description']}")
    if not lines:
        return (
            f"{_NO_CONTEXT} Não consegui gerar cenários "
            f"{'de borda' if wants_boundary else ''} a partir das regras disponíveis para esse campo."
        )
    kind = "positivos" if wants_positive else "negativos" if wants_negative else "de borda/valor"
    return f"Cenários {kind} sugeridos (revise e aprove antes de rodar):\n" + "\n".join(lines)


def _chat_generate_massa(message: str, context: dict) -> str:
    variables = _chat_request_field_names(context)
    if not variables:
        return (
            f"{_NO_CONTEXT} Não encontrei campos no body/URL desta API para basear uma massa. Use o botão "
            "'Gerar massa com IA' no painel de Massas de Teste, que analisa a API automaticamente."
        )
    count_match = _CHAT_COUNT_RE.search(message)
    count = min(int(count_match.group(1)), 50) if count_match else 5
    data = _build_test_data(variables, count)
    header = ",".join(data["columns"])
    rows = "\n".join(",".join(str(row.get(c, "")) for c in data["columns"]) for row in data["rows"])
    return (
        f"Massa sugerida com {count} caso(s) — revise antes de salvar/executar (use 'Gerar massa com IA' no "
        f"painel de Massas para confirmar):\n\n{header}\n{rows}"
    )


def _heuristic_chat(message: str, context: dict) -> str:  # noqa: C901 - dispatcher de intenção, complexidade é inerente
    """Implementação do Assistente de IA (chat) para o provider padrão -
    determinística, mas com reconhecimento de intenção estruturado (não
    apenas algumas frases fixas): explica API/request/response, lista
    campos e tipos, sugere regras/cenários/massa a partir do contexto real,
    explica status HTTP e falhas. Não sustenta uma conversa livre de
    verdade (isso exige um LLM real, ver app/ai/openai_provider.py) - quando
    falta contexto ou a pergunta não é reconhecida, é honesta em vez de
    inventar uma resposta."""
    norm = _strip_accents(message.strip().lower())

    status = context.get("status_code")
    body = context.get("body_json")
    url = context.get("url")
    method = context.get("method")
    rules = context.get("rules") or []
    execution_result = context.get("execution_result")

    # 1) status HTTP explícito mencionado na pergunta ("explique esse 401") ---
    status_match = _CHAT_HTTP_STATUS_RE.search(message)
    if status_match and _CHAT_EXPLAIN_RE.search(message):
        code = int(status_match.group(1))
        explanation = friendly_status_message(code)
        if explanation:
            return explanation
        if code < 400:
            return f"HTTP {code} não é um código de erro — indica sucesso ou redirecionamento."

    # 1.5) "qual foi o status HTTP" (sem número explícito na pergunta) - exige
    # "http"/"codigo" junto de "status" para não colidir com um CAMPO de
    # negócio chamado "status" (ex: "qual o valor do campo status"), que é
    # tratado mais abaixo pelo answer_question genérico.
    if "status" in norm and not status_match and _chat_has(norm, "http", "codigo"):
        return f"O status HTTP observado foi {status}." if status is not None else _NO_CONTEXT

    # 2) timeout -----------------------------------------------------------------
    if _chat_has(norm, "timeout", "tempo limite", "nao respondeu", "demorou"):
        error = context.get("error") or ""
        if "tempo limite" in error.lower() or "timeout" in norm:
            detail = f" (observado agora: {error})" if error else ""
            return (
                "Timeout significa que o TestFlow não recebeu resposta da API dentro do tempo configurado"
                f"{detail}. Isso normalmente indica que a API está lenta, sobrecarregada ou fora do ar — não é "
                "um problema do TestFlow."
            )

    # 3) falha de teste / diferença esperado vs atual ----------------------------
    if _chat_has(norm, "falhou", "falha", "quebrou") or (_chat_has(norm, "diferenc") and "esperado" in norm):
        if execution_result:
            field = execution_result.get("field") or "(verificação global)"
            expected, actual = execution_result.get("expected"), execution_result.get("actual")
            return (
                f"O teste em '{field}' esperava {expected!r}, mas a resposta observada trouxe {actual!r}. "
                "Verifique se a regra ainda reflete o contrato atual da API ou se os dados do ambiente de teste "
                "mudaram."
            )
        return (
            f"{_NO_CONTEXT} Abra o resultado da execução e use o botão 'Explicar esta falha' para uma análise "
            "focada nesse teste específico."
        )

    # 4) criar/sugerir regras para campo(s) mencionado(s) -------------------------
    if "regra" in norm and _chat_has(norm, "crie", "cria", "sugir", "sugest", "adicion", "gerar"):
        if not isinstance(body, dict) or not body:
            return f"{_NO_CONTEXT} Clique em 'Testar API' primeiro para eu ter uma resposta real para analisar."
        known_fields = _flatten_field_paths(body)
        mentioned = _chat_fields_mentioned(message, known_fields)
        target_fields = mentioned or [k for k in body if not isinstance(body[k], dict | list)][:5]
        suggestions = [_chat_suggest_rule_for_field(f, body) for f in target_fields]
        if not suggestions:
            return f"{_NO_CONTEXT} Não identifiquei nenhum campo mencionado na resposta real desta API."
        lines = "\n".join(f"- {s}" for s in suggestions)
        return (
            f"Regras sugeridas a partir da resposta observada (revise e aprove no painel de regras):\n{lines}"
        )

    # 5) regra "está correta"? (julgamento semântico - honesto sobre o limite) ----
    if "regra" in norm and _chat_has(norm, "correta", "certa", "faz sentido"):
        return (
            "A IA heurística confirma que uma regra é sintaticamente válida (campo/operador/valor reconhecidos "
            "na resposta real), mas julgar se ela está 'correta' para o seu negócio exige entender o domínio da "
            "API — isso precisa de um LLM real (configure API_TESTFLOW_AI_PROVIDER=openai) ou de revisão humana."
        )

    # 6) explicar/listar as regras já aprovadas ------------------------------------
    if "regra" in norm and _chat_has(norm, "explic", "expliqu", "quais", "liste", "listar"):
        if not rules:
            return f"{_NO_CONTEXT} Nenhuma regra aprovada ainda para esta API."
        lines = "\n".join(f"- {r.get('field')} {r.get('operator')} {r.get('expected')!r}" for r in rules)
        return f"Regras já aprovadas para esta API ({len(rules)}):\n{lines}"

    # 7) cenários (positivos/negativos/borda) --------------------------------------
    if _chat_has(norm, "cenario", "caso de teste", "casos de teste"):
        return _chat_scenarios_for_rules(message, rules, norm)

    # 8) massa de teste ---------------------------------------------------------------
    if "massa" in norm:
        return _chat_generate_massa(message, context)

    # 9) campos importantes / o que validar --------------------------------------------
    if _chat_has(norm, "important") or ("campo" in norm and "valida" in norm):
        if not isinstance(body, dict) or not body:
            return f"{_NO_CONTEXT} Clique em 'Testar API' primeiro."
        result = HeuristicAIProvider().suggest_from_response({"body_json": body, "status_code": status}, [])
        fields = sorted({s["field"] for s in result["suggestions"] if s.get("field")})
        if fields:
            return f"{result['summary']} Campos que parecem relevantes para validar: {', '.join(fields)}."
        return result["summary"] or "Não identifiquei campos que se destaquem automaticamente nesta resposta."

    # 10) perguntas pontuais sobre a RESPONSE (tipo/valor/existe/campos dentro de X) —
    # reaproveita answer_question, que já cobre esses padrões com precisão; só usa
    # o resultado se ele reconheceu algo específico (não a mensagem genérica dele).
    if isinstance(body, dict) and body:
        candidate = HeuristicAIProvider().answer_question(message, {"body_json": body, "json_valid": True})
        if not candidate.startswith("Não entendi exatamente"):
            return candidate

    # 11) autenticação -------------------------------------------------------------------
    if _chat_has(norm, "autentic", "token", "bearer", "login"):
        auth_type = context.get("auth_type")
        if auth_type is None:
            return _NO_CONTEXT
        if auth_type == "none":
            return "Esta API está configurada SEM autenticação (auth type = none)."
        return f"Esta API está configurada com autenticação do tipo '{auth_type}'."

    # 12) request possui body? ------------------------------------------------------------
    if ("body" in norm or "corpo" in norm) and _chat_has(norm, "tem", "possui", "existe", "ha "):
        request_body = context.get("request_body")
        if "request_body" not in context and "method" not in context:
            return _NO_CONTEXT
        return "Sim, esta requisição envia um body." if request_body else "Não, esta requisição não possui body."

    # 13) headers relevantes ----------------------------------------------------------------
    if "header" in norm or "cabecalho" in norm:
        req_headers = context.get("request_headers") or {}
        resp_headers = context.get("headers") or {}
        if not req_headers and not resp_headers:
            return _NO_CONTEXT
        parts = []
        if req_headers:
            parts.append(f"Headers enviados: {', '.join(req_headers.keys())}.")
        if resp_headers:
            parts.append(f"Headers recebidos: {', '.join(list(resp_headers.keys())[:15])}.")
        return " ".join(parts)

    # 14) método HTTP -----------------------------------------------------------------------
    if "metodo" in norm:
        return f"Esta API usa o método {method}." if method else _NO_CONTEXT

    # 15) URL ---------------------------------------------------------------------------------
    if _chat_has(norm, " url", "endereco") or norm.startswith("url"):
        return f"A URL desta API é {url}." if url else _NO_CONTEXT

    # 16) listar campos do REQUEST ------------------------------------------------------------
    if "campo" in norm and _chat_has(norm, "request", "enviad", "mandei", "mandou"):
        names = _chat_request_field_names(context)
        if names:
            return f"Campos identificados no request: {', '.join(names)}."
        request_body = context.get("request_body")
        return "O request não possui body." if "request_body" in context and not request_body else _NO_CONTEXT

    # 17) listar campos da RESPONSE -----------------------------------------------------------
    if "campo" in norm and _chat_has(norm, "response", "resposta", "retorno", "retornou"):
        if isinstance(body, dict) and body:
            return f"Campos da response: {_chat_field_summary(body)}."
        return _NO_CONTEXT

    # 18) explicar o REQUEST -------------------------------------------------------------------
    if _chat_has(norm, "request", "enviei", "mandei") and _chat_has(norm, "explic", "expliqu", "o que"):
        return _chat_describe_request(context)

    # 19) explicar a RESPONSE -------------------------------------------------------------------
    mentions_response = _chat_has(norm, "response", "resposta", "retornou", "recebeu", "devolveu")
    if mentions_response and _CHAT_EXPLAIN_RE.search(norm):
        return _chat_describe_response(context)

    # 20) "explique o que foi enviado e recebido" (combinado) -----------------------------------
    if _chat_has(norm, "enviado") and _chat_has(norm, "recebid", "retornou"):
        return f"{_chat_describe_request(context)}\n{_chat_describe_response(context)}"

    # 21) explicar a API de forma geral (catch-all mais amplo) ----------------------------------
    if _CHAT_EXPLAIN_RE.search(norm) and _chat_has(norm, "api", "endpoint", "essa chamada"):
        parts = []
        if method and url:
            parts.append(f"Esta é uma chamada {method} para {url}.")
        if status is not None:
            parts.append(f"A última resposta observada teve status HTTP {status}.")
        if isinstance(body, dict) and body:
            parts.append(f"Campos da response: {_chat_field_summary(body)}.")
        if context.get("request_body"):
            parts.append("O request enviado possui body (pergunte 'explique o request' para ver os detalhes).")
        if rules:
            parts.append(f"Há {len(rules)} regra(s) de negócio já aprovada(s) para esta API.")
        if not parts:
            return f"{_NO_CONTEXT} Clique em 'Testar API' primeiro."
        return " ".join(parts)

    # 22) último recurso: se há uma resposta real, tenta achar algo que bata -------------------
    if isinstance(body, dict) and body:
        return HeuristicAIProvider().answer_question(message, {"body_json": body, "json_valid": True})

    return (
        "Não reconheci essa pergunta com o provider heurístico atual (determinístico, sem LLM real). Tente "
        "reformular usando termos como 'explique', 'campos', 'regras', 'cenários', 'massa', 'status' ou "
        "'autenticação' — ou configure API_TESTFLOW_AI_PROVIDER=openai para uma conversa livre de verdade."
    )


def _sample_value_for_variable(name: str, index: int) -> Any:
    """Gera UM valor plausível para uma variável de massa, pelo NOME dela -
    puramente heurístico/genérico (não é um dicionário de dados de nenhum
    cliente): so reconhece padrões comuns de nome de campo, do mesmo jeito
    que _SYNONYMS já faz para regras em português."""
    norm = _strip_accents(name.strip().lower())

    if re.search(r"\bid$|_id$|^id\b", norm):
        return index + 1
    if "cpf" in norm:
        return f"{10000000000 + index * 111111111 % 89999999999}"
    if "idade" in norm or norm == "age":
        return [0, 17, 18, 30, 65][index % 5]
    if "email" in norm or "mail" in norm:
        return f"teste{index + 1}@exemplo.com"
    if re.search(r"valor|preco|price|amount", norm):
        return (index + 1) * 1000
    if re.search(r"nome|name", norm):
        return f"Usuário Teste {index + 1}"
    if re.search(r"ativo|active|habilitado|enabled", norm):
        return index % 2 == 0
    if re.search(r"telefone|phone", norm):
        return f"119{80000000 + index}"
    if re.search(r"resultado|status|situacao|estado", norm):
        return "aprovado" if index % 2 == 0 else "recusado"
    return f"valor_teste_{index + 1}"


def _build_test_data(variables: list[str], count: int) -> dict:
    count = max(1, min(count, 200))  # limite defensivo - a IA nunca gera uma massa gigante sem o usuario pedir
    rows = [{var: _sample_value_for_variable(var, i) for var in variables} for i in range(count)]
    return {"columns": list(variables), "rows": rows}
