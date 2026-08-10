"""
Parser DETERMINISTICO para regras tecnicas explicitas (ex: "stargazers_count
> 100", "private == false", 'name == "Hello-World"').

Por que existe separado da IA (ver REGRA DE ARQUITETURA do pedido que criou
este arquivo): quando o usuario ja escreve a expressao tecnica diretamente,
nao ha ambiguidade de linguagem natural para resolver - interpretar isso
com heuristicas/IA seria mais lento e arriscado do que necessario. Este
parser e usado ANTES da IA (ver app/api/ai.py) e, se a entrada inteira for
sintaxe tecnica reconhecida, a IA nem chega a ser chamada. Produz
exatamente a mesma estrutura de regra que app.ai.heuristic_provider usa,
entao dali em diante (aprovacao, pytest, PASS/FAIL) tudo continua igual.
"""

from __future__ import annotations

import re
import uuid

_TECH_RULE_RE = re.compile(r"^(?P<field>[A-Za-z_][\w.]*)\s*(?P<op>==|!=|>=|<=|>|<)\s*(?P<value>.+)$")

_TECH_OP_MAP = {
    "==": "equals",
    "!=": "not_equals",
    ">=": "greater_than_or_equal",
    "<=": "less_than_or_equal",
    ">": "greater_than",
    "<": "less_than",
}


def _clean_tech_value(raw: str) -> str | int | float | bool:
    v = raw.strip().strip(".").strip(",").strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    low = v.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    return v


def is_technical_line(line: str) -> bool:
    """True se a linha parece sintaxe tecnica explicita (tem um operador
    tecnico como ==, !=, >=, <=, >, <). Frases em linguagem natural em
    portugues praticamente nunca usam esses simbolos, entao isto raramente
    "sequestra" uma frase natural por engano."""
    return _TECH_RULE_RE.match(line.strip()) is not None


def parse_technical_line(line: str, known_fields: list[str]) -> dict | None:
    """Retorna None se a linha nao e sintaxe tecnica (o chamador deve usar
    o caminho de linguagem natural/IA nesse caso). Se for sintaxe tecnica
    mas o campo nao existir de verdade na resposta, retorna
    {"unresolved": True, "candidate": ...} - nunca inventa o campo, mesma
    regra fundamental da interpretacao por linguagem natural."""
    m = _TECH_RULE_RE.match(line.strip())
    if not m:
        return None

    field_raw = m.group("field")
    operator = _TECH_OP_MAP[m.group("op")]
    expected = _clean_tech_value(m.group("value"))

    if known_fields:
        norm = field_raw.strip().lower()
        match = next((f for f in known_fields if f.lower() == norm), None)
        if match is None:
            return {"unresolved": True, "candidate": field_raw}
        field = match
    else:
        field = field_raw

    return {"field": field, "operator": operator, "expected": expected}


def parse_multiple_lines(text: str, known_fields: list[str]) -> dict:
    """Função 1 do Assistente de IA ("Gerar regras"): cada linha DEVE ser
    sintaxe técnica explícita (campo operador valor) com um nome de campo
    REAL. Diferente de app.ai.heuristic_provider.nl_to_rules (Função 2 -
    "Analisar requisito", que interpreta linguagem natural), esta função é
    deliberadamente determinística e NÃO tenta interpretar nem "adivinhar"
    nada: uma linha que não segue o formato, ou que cita um campo que não
    existe na resposta, sempre vira um erro claro - nunca um campo
    inventado nem uma tentativa de correspondência aproximada."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    rules: list[dict] = []
    errors: list[str] = []
    for line in lines:
        if not is_technical_line(line):
            errors.append(
                f'Linha não reconhecida: "{line}". Use o formato campo operador valor '
                f"(ex: stargazers_count > 100)."
            )
            continue
        parsed = parse_technical_line(line, known_fields)
        if parsed.get("unresolved"):
            candidate = parsed["candidate"]
            errors.append(f'Campo "{candidate}" não encontrado na resposta da API. Use o nome real do campo.')
            continue
        rules.append(build_technical_rule(parsed, line))
    return {"rules": rules, "errors": errors}


def build_technical_rule(parsed: dict, raw_text: str) -> dict:
    field = parsed["field"]
    operator = parsed["operator"]
    expected = parsed["expected"]
    return {
        "id": str(uuid.uuid4()),
        # source="custom": o usuario escreveu a regra tecnica diretamente,
        # nao houve interpretacao/inferencia da IA sobre ela.
        "source": "custom",
        "category": "http" if field.startswith("$.") else "field",
        "field": field,
        "operator": operator,
        "expected": expected,
        "description": f"{field} {operator} {expected if expected is not None else ''}".strip(),
        "confidence": 1.0,
        "raw_text": raw_text,
    }
