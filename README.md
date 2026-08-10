# 🧪 API TestFlow

Plataforma universal de testes automatizados de API, com **pytest** como motor de execução e uma **IA opcional** como consultora. Criada para que qualquer squad teste qualquer API — sem escrever Python, pytest, YAML ou Swagger.

> Este README também serve como material didático: além de "como usar", cada seção explica **por que** aquela parte existe.

---

## Índice

1. [Instalação](#1-instalação)
2. [Execução](#2-execução)
3. [Execução via Docker](#3-execução-via-docker)
4. [Arquitetura](#4-arquitetura)
5. [Estrutura de pastas](#5-estrutura-de-pastas)
6. [Fluxo de uso completo](#6-fluxo-de-uso-completo)
7. [Como importar cURL](#7-como-importar-curl)
8. [Como importar Bruno](#8-como-importar-bruno)
9. [Descoberta automática vs. regras de negócio](#9-descoberta-automática-vs-regras-de-negócio)
10. [Como usar a IA](#10-como-usar-a-ia-e-como-executar-sem-ela)
11. [pytest como motor de execução](#11-pytest-como-motor-de-execução)
12. [Como interpretar o dashboard](#12-como-interpretar-o-dashboard)
13. [Segurança](#13-segurança)
14. [Como adicionar novas validações (operadores)](#14-como-adicionar-novas-validações-operadores)
15. [Como adicionar novos AI providers](#15-como-adicionar-novos-ai-providers)
16. [Testes do próprio projeto](#16-testes-do-próprio-projeto)
17. [Limitações conhecidas e próximos passos](#17-limitações-conhecidas-e-próximos-passos)

---

## 1. Instalação

### Pré-requisitos
- Python 3.12+
- Node.js 20+
- (Opcional) Docker + Docker Compose
- (Opcional) [Ollama](https://ollama.com) rodando localmente, se quiser IA generativa de verdade em vez da IA heurística embutida

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Frontend

```bash
cd frontend
npm install
```

---

## 2. Execução

Em dois terminais separados:

```bash
# Terminal 1 — backend (FastAPI)
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend (React + Vite)
cd frontend
npm run dev
```

Abra **http://localhost:5173**. O Vite já está configurado (`vite.config.ts`) para fazer proxy de `/api/*` para `http://127.0.0.1:8000`, então o frontend nunca precisa saber a URL do backend em produção nem se preocupar com CORS em dev.

O terminal só é necessário para **subir** os dois serviços. Depois disso, **todo o uso é pelo navegador** — criar projeto, testar API, importar cURL/Bruno, adicionar regras, pedir sugestões de IA e rodar os testes.

---

## 3. Execução via Docker

```bash
docker compose up --build
```

- Frontend: **http://localhost:8080**
- Backend: **http://localhost:8000**

O `docker-compose.yml` sobe dois serviços (`backend` com FastAPI+pytest, `frontend` com Nginx servindo o build estático e fazendo proxy de `/api` para o backend) e um volume nomeado (`api_testflow_data`) onde ficam o banco SQLite e a chave de criptografia — isso garante que os dados sobrevivem a `docker compose down` (mas não a `docker compose down -v`).

Para usar Ollama junto de Docker, aponte `API_TESTFLOW_OLLAMA_URL` para o host que roda o Ollama (em Docker Desktop, geralmente `http://host.docker.internal:11434`) e mude `API_TESTFLOW_AI_PROVIDER` para `ollama` no `docker-compose.yml`.

---

## 4. Arquitetura

```
┌─────────────┐      HTTP       ┌──────────────────────────────────────────┐
│   Frontend  │ ───────────────▶│                 Backend (FastAPI)         │
│ React + TS  │◀─────────────── │                                           │
└─────────────┘                 │  ┌────────────┐  ┌───────────────────┐    │
                                 │  │  Discovery  │  │   AI Provider     │    │
                                 │  │  Engine     │  │  (heuristic/ollama)│   │
                                 │  └────────────┘  └───────────────────┘    │
                                 │  ┌────────────┐  ┌───────────────────┐    │
                                 │  │ cURL/Bruno  │  │  Rule Evaluator   │    │
                                 │  │  Importers  │  │  (shared module)  │    │
                                 │  └────────────┘  └─────────┬─────────┘    │
                                 │                              │            │
                                 │                    ┌─────────▼─────────┐  │
                                 │                    │  pytest Runner    │  │
                                 │                    │  (subprocess)      │  │
                                 │                    └─────────┬─────────┘  │
                                 └──────────────────────────────┼────────────┘
                                                                 │
                                                     ┌───────────▼───────────┐
                                                     │  API real (qualquer)  │
                                                     └────────────────────────┘
                                 │
                            ┌────▼────┐
                            │ SQLite  │  (projetos, requisições, regras,
                            └─────────┘   execuções, resultados)
```

### Por que essa separação existe (seção 2 do spec original)

O sistema separa três responsabilidades que **nunca se misturam**:

| Camada | Responsabilidade | O que NUNCA faz |
|---|---|---|
| **API TestFlow** (backend+frontend) | UI, configuração, descoberta automática, orquestração | Decidir PASS/FAIL sozinho |
| **IA** (`app/ai/`) | Sugerir testes, explicar falhas, converter linguagem natural em regras | Decidir PASS/FAIL, alterar um teste sem aprovação |
| **pytest** (`app/engine/pytest_project/`) | Executar o assert e produzir PASS/FAIL | Ser substituído por um "mecanismo paralelo" de resultado |

Esse desenho não é só um princípio de design — é **imposto pela arquitetura**: o `AIProvider` (`app/ai/base.py`) não tem nenhum método que retorna um veredito de teste, só sugestões que o **usuário precisa aprovar** clicando em "Adicionar" antes de virarem uma `Rule` no banco. E o backend nunca decide PASS/FAIL diretamente — ele só lê o relatório JSON que o **pytest** gerou (`app/engine/pytest_runner.py`).

### Por que os testes rodam em um **subprocesso** pytest, e não in-process

Duas razões:
1. **Isolamento**: cada execução roda em um processo próprio, evitando que estado de uma execução vaze para outra (importante quando squads diferentes testam ao mesmo tempo).
2. **Segurança**: os dados da regra (URL, headers, valores esperados) vêm de squads diferentes testando APIs arbitrárias. Em vez de **gerar código Python dinamicamente** com esses dados (um risco real de injeção de código), o backend escreve um arquivo **JSON** ("spec") com a requisição e os checks, e um módulo pytest **fixo** (`test_rules.py`) lê esse JSON e usa `pytest_generate_tests` para criar um teste parametrizado por check. Nenhum dado do usuário jamais vira texto de código-fonte.

Veja `app/engine/pytest_project/conftest.py` para os comentários completos sobre esse desenho.

---

## 5. Estrutura de pastas

```
API TestFlow/
├── backend/
│   ├── app/
│   │   ├── main.py                 # monta o FastAPI app e os routers
│   │   ├── core/
│   │   │   ├── config.py           # configuração via variáveis de ambiente
│   │   │   └── security.py         # criptografia/mascaramento de segredos
│   │   ├── db/
│   │   │   ├── models.py           # Project, ApiRequestDef, Rule, Execution, TestResult
│   │   │   └── database.py         # engine SQLite (SQLModel)
│   │   ├── engine/
│   │   │   ├── http_executor.py    # executa a requisição real (httpx)
│   │   │   ├── discovery.py        # descoberta automática de validações técnicas
│   │   │   ├── evaluator.py        # avalia UM check (compartilhado com o pytest)
│   │   │   ├── curl_import.py      # parser de cURL
│   │   │   ├── bruno_import.py     # parser de .bru (Bruno)
│   │   │   ├── pytest_runner.py    # orquestra a execução real do pytest
│   │   │   └── pytest_project/     # o "projeto pytest" real (conftest + test_rules.py)
│   │   ├── ai/
│   │   │   ├── base.py             # interface AIProvider
│   │   │   ├── heuristic_provider.py  # IA padrão, 100% local, sem dependências
│   │   │   ├── ollama_provider.py  # IA opcional via Ollama
│   │   │   └── factory.py          # escolhe o provider pela configuração
│   │   ├── api/                    # routers FastAPI (projects, requests, rules, ai, executions, imports)
│   │   └── schemas.py              # contratos Pydantic da API HTTP
│   └── tests/                      # testes do próprio projeto (pytest)
├── frontend/
│   └── src/
│       ├── pages/                  # uma página por etapa do fluxo (ver seção 6)
│       ├── components/             # RuleBuilder, NlAssistant, ResponseViewer, ...
│       ├── lib/api.ts              # cliente HTTP tipado para o backend
│       └── types/                  # tipos TS espelhando os schemas do backend
├── docker-compose.yml
└── .github/workflows/ci.yml
```

---

## 6. Fluxo de uso completo

### Como criar um projeto (squad)

Na tela inicial (`/`), clique em **"+ Criar projeto"**, dê um nome (ex: "Vivo", "Porto", "Claro") e confirme. Projetos são um agrupamento simples — cada um tem suas próprias APIs testadas e regras, sem nenhuma configuração corporativa complexa por trás.

### Como testar uma API (fluxo manual)

1. Abra um projeto → **"🚀 Testar nova API"**.
2. Preencha **método** e **URL**. Headers, query params, body e autenticação ficam atrás de "+ Mostrar" — avançado, mas nunca obrigatório.
3. Clique em **"🚀 TESTAR API"**. Isso salva a definição da requisição e (se o método for seguro, como GET) já dispara a chamada real.
4. Você cai na tela de trabalho (`WorkbenchPage`), com a resposta, as validações descobertas automaticamente, o construtor de regras, o assistente de IA e o botão para executar os testes.

---

## 7. Como importar cURL

Na tela "Testar sua API", aba **"📥 Importar cURL"**, cole um comando como:

```bash
curl --location 'https://api.exemplo.com/clientes/123' \
--header 'Authorization: Bearer TOKEN' \
--header 'Content-Type: application/json'
```

Clique em **"Converter cURL"**. O backend (`app/engine/curl_import.py`) reconhece `-X/--request`, `-H/--header`, `-d/--data*`, `-u/--user` (Basic Auth), `-b/--cookie`, query strings na URL, e detecta automaticamente `Authorization: Bearer ...` como autenticação Bearer estruturada. Os campos aparecem preenchidos para **revisão** — nada é executado até você clicar em "🚀 TESTAR API".

---

## 8. Como importar Bruno

O [Bruno](https://www.usebruno.com/) salva cada requisição como um arquivo texto `.bru` em formato de blocos (`meta{}`, `get{}`, `headers{}`, `body:json{}`, `auth:bearer{}`...). Esse é o formato **real** que o Bruno grava em disco — não um formato inventado por este projeto.

**Suportado:** importar o conteúdo de **um arquivo `.bru`** (uma requisição), com método, URL, query params, headers, body (`json`/`text`/`graphql`/`xml`) e autenticação (`bearer`/`basic`/`apikey`).

**Não suportado ainda:** importar uma **collection inteira** do Bruno (múltiplas pastas + `bruno.json` + arquivos de *environment*). Isso exigiria resolver variáveis `{{var}}` através de um grafo de arquivos de ambiente/coleção — uma complexidade bem maior do que interpretar uma única requisição. Em vez de implementar isso pela metade, o importador:
1. suporta bem o caso de requisição única, e
2. detecta variáveis `{{...}}` não resolvidas e avisa claramente na tela de revisão, para você preencher manualmente.

Veja o cabeçalho de `backend/app/engine/bruno_import.py` para o raciocínio completo.

---

## 9. Duas camadas: diagnóstico técnico vs. regras de negócio

A tela de trabalho (`WorkbenchPage`) é organizada em duas camadas deliberadamente separadas:

### Camada técnica automática — "Diagnóstico técnico"

Depois de testar a API, o card **"Diagnóstico técnico"** resume tudo que é observável tecnicamente:
HTTP status, JSON válido, Content-Type, tempo de resposta, quantos campos foram mapeados. Você **não
precisa marcar dezenas de checkboxes uma a uma** — um único botão **"Aceitar diagnóstico técnico"**
aprova tudo de uma vez; "+ Ver detalhes" expande a lista completa (id existe, id é integer, email tem
formato plausível...) para quem quiser refinar item a item. O motor por trás continua o mesmo
(`app/engine/discovery.py`) — só a apresentação deixou de ser uma parede de 40 checkboxes.

O motor de descoberta **nunca** infere uma regra de valor de negócio. Se a resposta trouxer
`"status": "ACTIVE"`, a descoberta gera `status existe` e `status é string` — **nunca**
`status == "ACTIVE"` automaticamente, porque isso é uma decisão de contrato de negócio, não um fato
técnico. Um teste (`backend/tests/test_discovery.py`) garante essa invariante.

### Camada de regras de negócio com IA — "🎯 O que você quer garantir?"

Esta é a área principal e visualmente central da tela. Descreva em português o que uma resposta
*correta* deveria garantir:

> Clientes PREMIUM devem estar ativos e ter limite maior que 1000.

A IA analisa a **resposta real** da última chamada testada e propõe regras estruturadas — incluindo
regras **condicionais sobre listas**: se a resposta tiver um array (ex: `customers`) e o valor
mencionado ("PREMIUM") realmente aparecer em algum campo de algum item desse array, a IA gera uma
regra do tipo "para cada item onde `tier = PREMIUM`, `active` deve ser `true` e `limit` deve ser maior
que `1000`". Ela **nunca inventa** uma condição sobre um valor que não foi observado na resposta real —
isso é o que a mantém genérica para qualquer API, em vez de um dicionário fixo de regras de negócio.
Você revisa e aprova cada regra proposta antes de qualquer coisa virar um teste de verdade
(`POST /rules` ou `/rules/bulk` — a IA nunca chama esses endpoints sozinha).

Regras condicionais são executadas pelo mesmo motor de sempre (`app/engine/evaluator.py`,
`_evaluate_array_check`): pytest continua sendo quem decide PASS/FAIL, e o resultado mostra quantos
itens satisfizeram a condição e quais falharam (ex: `4/5 itens OK — falhas: item[2]=180`).

### Consulta/análise sobre a resposta — "🤖 Pergunte sobre esta resposta"

Ao lado do JSON completo (que continua sempre visível, sem exigir aprovação de nada), há uma caixa de
pergunta livre: *"qual foi o retorno do campo elevation?"*, *"quais campos existem dentro de current?"*,
*"qual é o tipo de temperature_2m?"*. Isso é **consulta de leitura**, não um teste — a resposta nunca
vira uma Rule nem influencia PASS/FAIL (`AIProvider.answer_question`, rota `POST /ai/answer-question`).

---

## 10. Como usar a IA (e como executar sem ela)

A IA vive atrás de uma interface (`app/ai/base.py`, `AIProvider`) com métodos para: analisar respostas,
sugerir cenários negativos, converter linguagem natural em regras (incluindo condicionais sobre listas),
responder perguntas de consulta, e explicar falhas. **Nenhum desses métodos decide PASS/FAIL** — todos
retornam sugestões/respostas que você precisa aprovar (ou que são apenas informativas) antes de
influenciarem qualquer teste real.

### Provider padrão: heurístico (zero configuração)

Por padrão (`API_TESTFLOW_AI_PROVIDER=heuristic`), a plataforma usa `HeuristicAIProvider` — regras/regex
sobre texto em português, **sem nenhuma dependência externa, sem custo, sem rede**. Nomes de campo
mencionados em português (ex: "ativos", "limite") são resolvidos para os nomes reais observados na
resposta via um dicionário de sinônimos genérico (`_SYNONYMS` em `heuristic_provider.py`) — não é uma
lista de campos de nenhum cliente específico. É o que torna a frase "o sistema deve funcionar sem IA"
verdadeira na prática: essa IA **já vem pronta**, sem exigir instalar nada.

No painel **"🎯 O que você quer garantir?"**, digite algo como:

> Quero garantir que o status seja ACTIVE e que o id seja um número.

e clique em **"✨ GERAR REGRAS"**. O assistente propõe `status equals "ACTIVE"` e `id type_is "number"` — você marca quais quer e clica em **"Aprovar"**.

No painel **"🤖 Cenários negativos sugeridos"** (dentro de "Regras avançadas"), a IA analisa o método/URL/autenticação e sugere coisas como "ID inexistente → 404" ou "Sem autenticação → 401". Sugestões em métodos que alteram dados (POST/PUT/PATCH/DELETE) são sempre marcadas como exigindo confirmação explícita — a plataforma nunca dispara automaticamente uma chamada mutante só porque a IA sugeriu (seção 26 do spec original).

### Provider opcional: Ollama (modelo local de verdade)

Se você tiver o [Ollama](https://ollama.com) instalado e rodando (`ollama serve`, com algum modelo baixado, ex. `ollama pull llama3.2`):

```bash
export API_TESTFLOW_AI_PROVIDER=ollama
export API_TESTFLOW_OLLAMA_MODEL=llama3.2   # opcional, esse é o padrão
uvicorn app.main:app --reload
```

Se o Ollama não responder (não está rodando, endereço errado, etc.), **cada chamada cai automaticamente para o provider heurístico** — a ausência de IA "de verdade" nunca impede o uso da plataforma. Veja `app/ai/ollama_provider.py`.

### Segredos nunca vão para a IA

Headers sensíveis (`Authorization`, `Cookie`, `X-API-Key`...) são mascarados **antes** de qualquer payload ser montado para um provider de IA (`mask_headers` em `app/core/security.py`, aplicado em `app/api/ai.py`).

---

## 11. pytest como motor de execução

Quando você clica em **"▶ Executar testes"**:

1. O backend busca todas as `Rule` habilitadas daquela requisição (`app/api/executions.py`).
2. Monta um "spec": a definição da requisição + a lista de checks, e grava em um arquivo JSON temporário.
3. Roda `python -m pytest app/engine/pytest_project/test_rules.py --json-report ...` como **subprocesso**.
4. `conftest.py` lê o spec, faz a chamada HTTP **uma única vez** (fixture de sessão) e usa `pytest_generate_tests` para criar um teste parametrizado por check.
5. `test_rules.py` chama `evaluate_check(...)` (o mesmo módulo usado para pré-visualizar "observado" na UI) e faz um `assert` de verdade — é esse assert que decide PASS/FAIL.
6. O backend lê o relatório JSON produzido pelo **pytest** (via [`pytest-json-report`](https://pypi.org/project/pytest-json-report/)) e grava os resultados no banco. Ele nunca calcula PASS/FAIL por conta própria.

### Como executar pytest manualmente (fora da UI)

Para depurar ou entender o mecanismo, dá pra rodar pytest à mão contra qualquer spec:

```bash
cd backend
cat > /tmp/spec.json << 'EOF'
{
  "request": {"method": "GET", "url": "https://dummyjson.com/users/1", "headers": {}, "query_params": {}, "body": null, "body_type": "none", "auth": {"type": "none"}},
  "checks": [{"id": "c1", "field": "id", "operator": "type_is", "expected": "integer", "category": "field"}]
}
EOF
API_TESTFLOW_SPEC_FILE=/tmp/spec.json API_TESTFLOW_RESULTS_FILE=/tmp/results.jsonl \
  python -m pytest app/engine/pytest_project/test_rules.py -v
```

---

## 12. Como interpretar o dashboard

Depois da execução você é levado para a tela de resultado:

- **Cartões de resumo**: total de testes, 🟢 passed, 🔴 failed, ⚪ skipped, duração — vêm diretamente do relatório do pytest, não de uma contagem própria do backend.
- **Lista de testes**: cada linha é clicável.
- **Detalhe do teste**: mostra **Expected** vs **Actual** lado a lado (a comparação central do spec original), a mensagem bruta do pytest, e — se o teste falhou — um painel **"🤖 AI ANALYSIS"** com um botão para pedir à IA uma explicação da falha e possíveis próximos passos de investigação. A IA só explica; ela nunca decide se o teste passou.
- **📜 Histórico**: todas as execuções anteriores daquela API, com data, passed/failed/duração — clique em "ver detalhes" para reabrir qualquer execução passada.

---

## 13. Segurança

- Tokens, senhas e API keys são **criptografados** (Fernet/AES simétrico, `app/core/security.py`) antes de ir para o SQLite — nunca em texto puro.
- A chave de criptografia é gerada automaticamente na primeira execução (`backend/.secret_key`, fora do controle de versão) ou pode vir de `API_TESTFLOW_SECRET_KEY` / `API_TESTFLOW_SECRET_KEY_FILE`.
- Na interface e em qualquer payload enviado a um provider de IA, segredos aparecem **mascarados** (`Bearer eyJhbG...********`).
- Operações que alteram dados (POST/PUT/PATCH/DELETE) exigem confirmação explícita (`confirm=true`) tanto para "Testar API" quanto para "Executar testes" — a IA sugerindo um cenário negativo mutante nunca dispara a chamada sozinha.

---

## 14. Como adicionar novas validações (operadores)

Todo operador vive em **um único lugar**: `backend/app/engine/evaluator.py`, função `evaluate_check`. Para adicionar um operador novo (ex: `is_uuid_format`):

1. Adicione um `if operator == "is_uuid_format": ...` em `evaluate_check`, retornando um `EvalResult(passed, actual, expected, message)`.
2. Adicione a opção em `frontend/src/types/index.ts` (`OPERATORS`).
3. (Opcional) Adicione um teste em `backend/tests/test_evaluator.py`.

Como `test_rules.py` (o teste pytest real) e a pré-visualização da UI usam a **mesma** função, o novo operador funciona nos dois lugares automaticamente.

Para adicionar uma nova validação **automática** (descoberta), edite `backend/app/engine/discovery.py` — lembre-se da regra de ouro da seção 9: só adicione checks que sejam fatos técnicos observáveis, nunca valores de negócio.

---

## 15. Como adicionar novos AI providers

1. Crie uma classe em `backend/app/ai/` implementando `AIProvider` (`app/ai/base.py`): `suggest_from_response`, `suggest_negative_cases`, `nl_to_rules`, `explain_failure`.
2. Registre-a em `app/ai/factory.py` (`get_ai_provider`), associando a um valor de `API_TESTFLOW_AI_PROVIDER`.
3. Nunca envie segredos não mascarados para um serviço externo, e documente claramente se o provider depende de rede/serviço pago — o padrão da plataforma é funcionar 100% offline e gratuita.

---

## 16. Testes do próprio projeto

```bash
cd backend
pytest -q          # 21 testes: evaluator, discovery, cURL, Bruno, IA heurística
ruff check app tests
```

```bash
cd frontend
npm run build       # tsc -b (type-check) + vite build
```

---

## 17. Limitações conhecidas e próximos passos

Documentadas aqui de propósito, para não passar a impressão de que foram esquecidas:

- **Sem migrações de schema** (Alembic): mudanças no modelo exigem recriar o SQLite em dev. Aceitável para o estágio atual do projeto; adicionar Alembic é o próximo passo natural antes de um uso multiusuário sério.
- **Import de Bruno** cobre uma requisição por vez, não collections completas com environments (ver seção 8).
- **Cenários negativos sugeridos pela IA** são exibidos como sugestões de leitura (título, descrição, status esperado) — criar e executar automaticamente uma requisição alternativa (ex: com ID inválido) fica para uma iteração futura; hoje o usuário replica manualmente o cenário como uma nova requisição de teste.
- **Sem autenticação de usuário/multi-tenant**: adequado para um time rodando localmente ou em um ambiente interno confiável, não para expor publicamente sem uma camada de auth na frente.
- **Regras condicionais sobre listas** (`array_path`/`condition_*`) hoje suportam uma única condição de filtro por regra, com `condition_operator` tipicamente `equals`. Condições compostas ("PREMIUM E ativo há mais de 1 ano") exigiriam encadear múltiplas regras ou um novo operador lógico — não implementado ainda.
- A detecção de condição pela IA heurística exige que o valor mencionado apareça **literalmente** (case-insensitive) em algum campo de algum item do array na resposta real observada; sinônimos/variações do valor (ex: "clientes premium" quando a API usa `"tier": "P"`) não são inferidos.
