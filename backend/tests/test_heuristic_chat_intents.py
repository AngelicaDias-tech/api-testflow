"""Provedor heurístico "mais completo" (melhoria "Heurístico mais
completo") - cobre reconhecimento de intenção estruturado sobre um
contexto real (modelado no exemplo do pedido: POST
https://dummyjson.com/products/add). Cada teste espelha uma das perguntas
de exemplo listadas na tarefa."""

from __future__ import annotations

from app.ai.heuristic_provider import HeuristicAIProvider

provider = HeuristicAIProvider()

CONTEXT = {
    "method": "POST",
    "url": "https://dummyjson.com/products/add",
    "status_code": 200,
    "json_valid": True,
    "body_json": {
        "id": 195,
        "title": "Notebook TestFlow",
        "price": 3500,
        "stock": 10,
        "category": "electronics",
    },
    "request_body": '{"title": "Notebook TestFlow", "price": 3500, "stock": 10, "category": "electronics"}',
    "request_headers": {"Content-Type": "application/json"},
    "auth_type": "none",
    "rules": [
        {"field": "price", "operator": "greater_than", "expected": 0},
        {"field": "stock", "operator": "greater_than_or_equal", "expected": 0},
    ],
}


def test_explique_essa_api():
    answer = provider.chat("Explique essa API.", CONTEXT)
    assert "POST" in answer
    assert "dummyjson.com/products/add" in answer


def test_qual_metodo_essa_api_usa():
    assert provider.chat("Qual método essa API usa?", CONTEXT) == "Esta API usa o método POST."


def test_o_que_foi_enviado_no_request():
    answer = provider.chat("O que foi enviado no request?", CONTEXT)
    assert "Notebook TestFlow" in answer
    assert "POST" in answer


def test_o_que_a_api_retornou():
    answer = provider.chat("O que a API retornou?", CONTEXT)
    assert "200" in answer
    assert "title" in answer


def test_quais_campos_existem_na_response():
    answer = provider.chat("Quais campos existem na response?", CONTEXT)
    for field in ("id", "title", "price", "stock", "category"):
        assert field in answer


def test_qual_e_o_tipo_do_campo_price():
    answer = provider.chat("Qual é o tipo do campo price?", CONTEXT)
    assert "integer" in answer


def test_quais_campos_eu_deveria_validar():
    answer = provider.chat("Quais campos eu deveria validar?", CONTEXT)
    assert "id" in answer  # heurística sempre sugere validar 'id'


def test_crie_regras_para_price_e_stock():
    answer = provider.chat("Crie regras para price e stock.", CONTEXT)
    assert "price greater_than 0" in answer
    assert "stock greater_than_or_equal 0" in answer  # 'stock' reconhecido como contador -> >= 0


def test_crie_cenarios_negativos():
    answer = provider.chat("Crie cenários negativos.", CONTEXT)
    assert "price" in answer
    assert "PASS" not in answer  # só os cenários FAIL, nenhum PASS misturado


def test_crie_casos_de_borda():
    answer = provider.chat("Crie casos de borda.", CONTEXT)
    assert "price" in answer


def test_por_que_esse_teste_falhou_sem_contexto_de_execucao():
    answer = provider.chat("Por que esse teste falhou?", CONTEXT)
    assert "Não tenho essa informação no contexto atual." in answer
    assert "Explicar esta falha" in answer


def test_por_que_esse_teste_falhou_com_contexto_de_execucao():
    ctx = {**CONTEXT, "execution_result": {"field": "stock", "expected": "10", "actual": "-1"}}
    answer = provider.chat("Por que esse teste falhou?", ctx)
    assert "stock" in answer
    assert "-1" in answer


def test_essa_api_possui_body():
    assert "Sim" in provider.chat("Essa API possui body?", CONTEXT)


def test_essa_api_usa_autenticacao():
    answer = provider.chat("Essa API usa autenticação?", CONTEXT)
    assert "SEM autenticação" in answer


def test_essa_api_usa_autenticacao_quando_tem_bearer():
    ctx = {**CONTEXT, "auth_type": "bearer"}
    answer = provider.chat("Essa API usa autenticação?", ctx)
    assert "bearer" in answer


def test_qual_foi_o_status_http():
    assert provider.chat("Qual foi o status HTTP?", CONTEXT) == "O status HTTP observado foi 200."


def test_crie_uma_massa_com_5_produtos():
    answer = provider.chat("Crie uma massa com 5 produtos.", CONTEXT)
    assert "title,price,stock,category" in answer
    assert len(answer.strip().splitlines()) >= 6  # header + 5 linhas de dados


def test_explique_esse_erro_401_continua_funcionando():
    answer = provider.chat("Explique esse erro 401.", CONTEXT)
    assert "token" in answer.lower()


# --- honestidade: nunca inventa quando falta contexto -----------------------


def test_nao_inventa_metodo_sem_contexto():
    assert provider.chat("Qual método essa API usa?", {}) == "Não tenho essa informação no contexto atual."


def test_nao_inventa_autenticacao_sem_contexto():
    assert provider.chat("Essa API usa autenticação?", {}) == "Não tenho essa informação no contexto atual."


def test_nao_inventa_regras_sem_regras_aprovadas():
    ctx = {**CONTEXT, "rules": []}
    answer = provider.chat("Quais são as regras dessa API?", ctx)
    assert "Não tenho essa informação no contexto atual." in answer


def test_nao_inventa_cenarios_sem_regras():
    ctx = {**CONTEXT, "rules": []}
    answer = provider.chat("Crie cenários positivos.", ctx)
    assert "Não tenho essa informação no contexto atual." in answer


def test_pergunta_nao_reconhecida_e_honesta_sobre_limitacao():
    answer = provider.chat("me conte uma piada sobre gatos", {})
    assert "Não reconheci essa pergunta" in answer or "heurístic" in answer.lower()
