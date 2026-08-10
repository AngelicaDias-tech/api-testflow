"""
Interface desacoplada de IA (secao 12 do spec).

Por que existe: a IA e uma CONSULTORA, nunca a autoridade de PASS/FAIL
(secao 14) - ela so sugere; pytest decide. Para isso ser garantido pela
arquitetura (nao so por convencao), nenhum metodo desta interface
retorna um veredito de teste; todos retornam SUGESTOES que a UI exige
que o usuario aprove explicitamente antes de virarem regras reais
(app.db.models.Rule).

Qualquer novo provedor (nuvem, outro modelo local, etc.) so precisa
implementar esta interface. O sistema deve continuar funcionando por
completo se nenhum provedor de IA estiver disponivel - por isso todo
metodo aqui tem uma implementacao heuristica padrao que nao depende de
rede nem de servicos externos (ver heuristic_provider.py).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def suggest_from_response(self, response_ctx: dict, discovered_checks: list[dict]) -> dict:
        """Retorna sugestoes adicionais (nao tecnicas) a partir de uma
        resposta real, ex: 'este array parece paginado, quer validar que
        nao vem vazio?'. Formato: {"summary": str, "suggestions": [check,...]}
        """

    @abstractmethod
    def suggest_negative_cases(self, request_def: dict) -> list[dict]:
        """Sugere cenarios negativos (404, 401, 400...). Para metodos
        mutantes (POST/PUT/PATCH/DELETE) cada sugestao DEVE vir marcada
        com requires_confirmation=True (secao 26)."""

    @abstractmethod
    def nl_to_rules(self, text: str, response_ctx: dict | None) -> dict:
        """Converte linguagem natural em regras estruturadas candidatas.

        Quando `response_ctx` e fornecido, a IA deve analisar a resposta
        REAL (nao inventar campos) para: (1) resolver nomes de campo
        mencionados em portugues para os nomes reais observados na
        resposta, e (2) detectar regras condicionais sobre listas (ex:
        "clientes PREMIUM devem estar ativos") apenas quando o valor
        mencionado (ex: "PREMIUM") realmente aparece em algum campo de
        algum item de um array da resposta - nunca inventando uma
        condicao que nao foi observada.

        Formato: {"rules": [...], "unparsed": [str,...]}. Cada rule pode
        opcionalmente trazer array_path/condition_field/condition_operator/
        condition_expected (ver app/engine/evaluator.py).
        """

    @abstractmethod
    def explain_failure(self, result: dict, response_ctx: dict | None) -> str:
        """Explica em linguagem natural por que um teste falhou."""

    @abstractmethod
    def answer_question(self, question: str, response_ctx: dict) -> str:
        """Responde uma pergunta de CONSULTA/ANALISE sobre a resposta real
        (ex: "qual o valor do campo elevation?", "quais campos existem
        dentro de current?"). Isto NUNCA cria uma Rule nem influencia
        PASS/FAIL - e so leitura/explicacao sobre o JSON observado."""

    @abstractmethod
    def suggest_scenarios(self, check: dict) -> list[dict]:
        """Funcao 2 do Assistente de IA: a partir de uma regra estruturada
        ja validada (field/operator/expected), sugere 2-3 CENARIOS de valor
        com o resultado esperado (PASS/FAIL) - nunca executa nada, e o
        usuario quem escolhe quais cenarios quer usar; o pytest quem de
        fato decide quando o cenario virar uma execucao real."""

    def is_available(self) -> bool:
        return True

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "available": self.is_available()}
