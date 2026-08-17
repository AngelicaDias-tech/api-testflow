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
11. [Massas de dados: testes orientados a dados (CSV)](#11-massas-de-dados-testes-orientados-a-dados-csv)
12. [Cenários: variáveis reutilizáveis](#12-cenários-variáveis-reutilizáveis)
13. [Exportar e importar projetos](#13-exportar-e-importar-projetos)
14. [pytest como motor de execução](#14-pytest-como-motor-de-execução)
15. [Como interpretar o dashboard](#15-como-interpretar-o-dashboard)
16. [Segurança](#16-segurança)
17. [Como adicionar novas validações (operadores)](#17-como-adicionar-novas-validações-operadores)
18. [Como adicionar novos AI providers](#18-como-adicionar-novos-ai-providers)
19. [Testes do próprio projeto](#19-testes-do-próprio-projeto)
20. [Limitações conhecidas e próximos passos](#20-limitações-conhecidas-e-próximos-passos)

---

## 1. Instalação

### Pré-requisitos
- Python 3.12+
- Node.js 20+
- (Opcional) Docker + Docker Compose
- (Opcional) uma `OPENAI_API_KEY` da OpenAI, se quiser IA generativa de verdade em vez da IA heurística embutida

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

# Terminal 2 — frontend (Angular)
cd frontend
npm start
```

Abra **http://localhost:4200**. O Angular CLI já está configurado (`frontend/proxy.conf.json`) para fazer proxy de `/api/*` para `http://127.0.0.1:8000`, então o frontend nunca precisa saber a URL do backend em produção nem se preocupar com CORS em dev.

O terminal só é necessário para **subir** os dois serviços. Depois disso, **todo o uso é pelo navegador** — criar projeto, testar API, importar cURL/Bruno, adicionar regras, pedir sugestões de IA e rodar os testes.

---

## 3. Execução via Docker

```bash
docker compose up --build
```

- Frontend: **http://localhost:8080**
- Backend: **http://localhost:8000**

O `docker-compose.yml` sobe dois serviços (`backend` com FastAPI+pytest, `frontend` com Nginx servindo o build estático e fazendo proxy de `/api` para o backend) e um volume nomeado (`api_testflow_data`) onde ficam o banco SQLite e a chave de criptografia — isso garante que os dados sobrevivem a `docker compose down` (mas não a `docker compose down -v`).

Para usar OpenAI junto de Docker, defina `OPENAI_API_KEY` (e, opcionalmente, `API_TESTFLOW_OPENAI_MODEL`) no ambiente do serviço `backend` e mude `API_TESTFLOW_AI_PROVIDER` para `openai` no `docker-compose.yml`.

---

## 4. Arquitetura

```
┌─────────────┐      HTTP       ┌──────────────────────────────────────────┐
│   Frontend  │ ───────────────▶│                 Backend (FastAPI)         │
│ Angular + TS│◀─────────────── │                                           │
└─────────────┘                 │  ┌────────────┐  ┌───────────────────┐    │
                                 │  │  Discovery  │  │   AI Provider     │    │
                                 │  │  Engine     │  │  (heuristic/openai)│   │
                                 │  └────────────┘  └───────────────────┘    │
                                 │  ┌────────────┐  ┌───────────────────┐    │
                                 │  │ cURL/Bruno  │  │  Rule Evaluator   │    │
                                 │  │  Importers  │  │  (shared module)  │    │
                                 │  └────────────┘  └─────────┬─────────┘    │
                                 │  ┌────────────┐             │             │
                                 │  │ CSV Import  │             │             │
                                 │  │ + Templating│             │             │
                                 │  └──────┬──────┘             │             │
                                 │         │           ┌────────▼─────────┐  │
                                 │         └──────────▶│  pytest Runner    │  │
                                 │                      │  (subprocess)     │  │
                                 │                      └─────────┬─────────┘  │
                                 └──────────────────────────────┼────────────┘
                                                                 │
                                                     ┌───────────▼───────────┐
                                                     │  API real (qualquer)  │
                                                     └────────────────────────┘
                                 │
                            ┌────▼────┐
                            │ SQLite  │  (projetos, requisições, regras,
                            └─────────┘   cenários, massas de dados,
                                          execuções, resultados)
```

### Por que essa separação existe (seção 2 do spec original)

O sistema separa três responsabilidades que **nunca se misturam**:

| Camada | Responsabilidade | O que NUNCA faz |
|---|---|---|
| **API TestFlow** (backend+frontend) | UI, configuração, descoberta automática, orquestração | Decidir PASS/FAIL sozinho |
| **IA** (`app/ai/`) | Sugerir testes, explicar falhas, converter linguagem natural em regras, responder perguntas em chat | Decidir PASS/FAIL, alterar um teste sem aprovação |
| **Templating** (`app/engine/templating.py`) | Substituir `{{variavel}}` por valores de um cenário/linha de massa de dados | Decidir PASS/FAIL, inventar um valor para uma variável não fornecida |
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
│   │   │   ├── http_executor.py    # executa a requisição real (httpx), monta o "sent snapshot"
│   │   │   ├── discovery.py        # descoberta automática de validações técnicas
│   │   │   ├── evaluator.py        # avalia UM check (compartilhado com o pytest)
│   │   │   ├── curl_import.py      # parser de cURL
│   │   │   ├── bruno_import.py     # parser de .bru (Bruno)
│   │   │   ├── csv_import.py       # parser/validação de CSV para massas de dados
│   │   │   ├── templating.py       # substitui {{variavel}} em request/checks (cenários e massas)
│   │   │   ├── pytest_runner.py    # orquestra a execução real do pytest
│   │   │   └── pytest_project/     # o "projeto pytest" real (conftest + test_rules.py)
│   │   ├── ai/
│   │   │   ├── base.py             # interface AIProvider
│   │   │   ├── heuristic_provider.py  # IA padrão, 100% local, sem dependências (inclui o chat)
│   │   │   ├── openai_provider.py  # IA opcional via OpenAI (LLM real), com fallback para a heurística
│   │   │   ├── context.py          # monta contexto seguro (headers mascarados) para as chamadas de IA
│   │   │   └── factory.py          # escolhe o provider pela configuração
│   │   ├── api/                    # routers FastAPI: projects, requests, rules, ai, executions,
│   │   │   │                       # datasets, scenarios, export_import, imports (curl/bruno)
│   │   │   └── _common.py          # lógica compartilhada de execução (run_and_persist_execution)
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── error_messages.py   # traduz erros técnicos (HTTP/pytest/validação) em mensagens amigáveis
│   │   └── schemas.py              # contratos Pydantic da API HTTP
│   └── tests/                      # testes do próprio projeto (pytest, 200+ casos)
├── frontend/
│   └── src/app/
│       ├── pages/                  # uma página por etapa do fluxo (ver seção 6), incluindo os
│       │   │                       # painéis do workbench: assistant-panel, datasets-panel,
│       │   │                       # scenarios-panel, business-rules-panel
│       ├── shared/                 # response-viewer, request-viewer, ...
│       ├── core/services/api.service.ts  # cliente HTTP tipado para o backend
│       └── core/models/            # tipos TS espelhando os schemas do backend
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
4. Você cai na tela de trabalho (`WorkbenchPage`), com o **request enviado** e a **resposta recebida** lado a lado (ambos com segredos mascarados), as validações descobertas automaticamente, o construtor de regras, o assistente de IA (`assistant-panel`, com abas Conversar/Regras/Cenários/Massa) e o botão para executar os testes.

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
interpretar um requisito em texto livre (`nl_to_rules`), responder perguntas de consulta e em **chat
livre** (`chat`), gerar massas de teste (`suggest_test_data`), e explicar falhas. **Nenhum desses
métodos decide PASS/FAIL** — todos retornam sugestões/respostas que você precisa aprovar (ou que são
apenas informativas) antes de influenciarem qualquer teste real.

Na tela de trabalho, todas essas funções ficam reunidas em um único painel — **"🤖 Assistente de IA"**
(`assistant-panel`) — organizado em abas: **Conversar** (chat livre), **Regras** (gerar regras a partir
de sintaxe técnica ou de um requisito em linguagem natural), **Cenários** (cenários negativos sugeridos)
e **Massa** (gerar dados de teste). Esse painel único substituiu dois componentes antigos e separados
("Pergunte sobre esta resposta" e o bloco de regras de IA dentro de "Regras de negócio").

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

No painel **"🤖 Cenários negativos sugeridos"** (aba "Cenários"), a IA analisa o método/URL/autenticação e sugere coisas como "ID inexistente → 404" ou "Sem autenticação → 401". Sugestões em métodos que alteram dados (POST/PUT/PATCH/DELETE) são sempre marcadas como exigindo confirmação explícita — a plataforma nunca dispara automaticamente uma chamada mutante só porque a IA sugeriu (seção 26 do spec original). Essas sugestões continuam sendo **texto informativo**: para de fato criar e rodar uma variação da requisição, use **Cenários** (seção 12) — um mecanismo separado, de autoria manual.

### "Analisar requisito" — regra a partir de linguagem natural

Diferente do "GERAR REGRAS" (que interpreta uma frase técnica curta, tipo "status deve ser ACTIVE"),
a aba **Regras → Analisar requisito** (`POST /api/ai/nl-to-rules`) manda um requisito mais livre para a
IA interpretar de fato — útil quando a frase não segue nenhum padrão técnico fixo. O resultado é o
mesmo: uma lista de regras propostas para você revisar e aprovar antes de virarem `Rule`.

### Conversar — chat livre sobre a API

Na aba **Conversar** (`POST /api/ai/chat`), você pode perguntar qualquer coisa sobre a requisição/resposta
testada em linguagem natural — "explique essa API", "por que esse teste falhou?", "o que significa
erro 401?". É **só leitura**: a resposta nunca vira uma `Rule`, nunca dispara uma chamada HTTP e nunca
decide PASS/FAIL. No provider heurístico, o chat reconhece um conjunto fixo de perguntas comuns
(status HTTP, timeout, diagnóstico de falha, campos da requisição/resposta, headers, autenticação,
método, URL...); se a pergunta não for reconhecida, ele avisa e sugere reformular ou usar o provider
OpenAI. **Não há histórico de conversa salvo no backend** — cada mensagem é respondida com o contexto
da requisição atual; o histórico que você vê na tela existe só no navegador, durante aquela sessão.

### Massa — gerar dados de teste com IA

Na aba **Massa** (`POST /api/ai/requests/{id}/suggest-test-data`), a IA sugere um conjunto de linhas de
dados de teste (valores para as variáveis `{{...}}` da requisição) a partir da resposta observada. Você
revisa e aprova antes de salvar — a aprovação cria uma **massa de dados** de verdade (seção 11), pronta
para ser executada linha a linha.

### Provider opcional: OpenAI (LLM real)

Se você tiver uma `OPENAI_API_KEY` válida:

```bash
export API_TESTFLOW_AI_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export API_TESTFLOW_OPENAI_MODEL=gpt-4o-mini      # opcional, esse é o padrão
export API_TESTFLOW_OPENAI_TIMEOUT=60             # opcional, segundos, esse é o padrão
uvicorn app.main:app --reload
```

Se a OpenAI não responder (sem chave, rede indisponível, erro de autenticação, etc.), **cada chamada cai automaticamente para o provider heurístico** — a ausência de IA "de verdade" nunca impede o uso da plataforma. Veja `app/ai/openai_provider.py`.

### Segredos nunca vão para a IA

Headers sensíveis (`Authorization`, `Cookie`, `X-API-Key`...) são mascarados **antes** de qualquer payload ser montado para um provider de IA (`mask_headers` em `app/core/security.py`, aplicado em `app/ai/context.py` e `app/api/ai.py`).

---

## 11. Massas de dados: testes orientados a dados (CSV)

Às vezes você quer rodar a **mesma** requisição e as **mesmas** regras várias vezes, cada vez com um
conjunto diferente de valores (ex: 20 CPFs diferentes, todos devendo retornar 200). É pra isso que
existe a aba **"📊 Massas de dados"** no workbench.

### Como funciona

1. A requisição e as regras usam placeholders `{{variavel}}` (ex: URL `https://api.exemplo.com/clientes/{{cpf}}`, ou uma regra `status equals {{status_esperado}}`).
2. Você cola ou faz upload de um **CSV** cuja primeira linha é o cabeçalho (os nomes das variáveis) e cada linha seguinte é um caso de teste. Clique em **"Analisar CSV"** — o backend (`app/engine/csv_import.py`) só faz o parse e a inferência de tipo (número/booleano/texto) de cada coluna, **nada é salvo ainda**.
3. Revise a prévia, dê um nome à massa e clique em **"Confirmar e salvar massa"** — isso persiste um `TestDataSet` (`POST /api/requests/{id}/datasets`).
4. Clique em **"▶ Executar massa"** — o backend roda a requisição **uma vez por linha**: cada linha vira uma `Execution` normal (mesmo motor pytest de sempre, `app/engine/templating.py` substitui as variáveis antes de cada chamada), e uma `BatchExecution` agrupa o total de casos/passed/failed. Se o método for mutante (POST/PUT/PATCH/DELETE), é exigida confirmação explícita, igual ao fluxo manual.
5. O resultado mostra o PASS/FAIL de cada linha, com link para o detalhe de cada execução individual.

Você também pode gerar uma massa automaticamente a partir da resposta observada, usando a aba
**Massa** do assistente de IA (seção 10) — a IA só sugere as linhas; salvar continua exigindo sua aprovação.

---

## 12. Cenários: variáveis reutilizáveis

Um **cenário** é um conjunto nomeado de valores para as variáveis `{{...}}` de uma requisição, sem
alterar a requisição salva. Diferente da massa de dados (que roda **várias** linhas de uma vez), um
cenário é pensado para casos pontuais que você quer poder reexecutar rapidamente — por exemplo, um
cenário "cliente sem permissão" com `{{token}} = token_sem_escopo`.

Na aba **"🧪 Cenários"**, defina um nome e as variáveis (chave/valor), salve, e clique em **"▶ Executar
cenário"** — o backend (`app/api/scenarios.py`) resolve os placeholders com `app/engine/templating.py`
e roda pelo mesmo caminho de sempre (pytest decide PASS/FAIL). O mesmo gate de confirmação para métodos
mutantes se aplica.

Isso preenche parcialmente a limitação antiga de "cenário negativo sugerido pela IA só existe como
texto": agora dá para materializar e reexecutar uma variação da requisição com um clique — mas a
criação do cenário ainda é manual; a IA não converte automaticamente uma sugestão de cenário negativo
em um `Scenario` executável (ver seção 20).

---

## 13. Exportar e importar projetos

Na tela de projetos, cada projeto tem um botão **"📤 exportar"** (baixa um `.json`) e existe um botão
global **"📥 Importar testes"** (lê um `.json` do seu computador).

- **Exportação** (`GET /api/projects/{id}/export`): inclui o projeto, todas as suas requisições
  (método/URL/headers/params/body/auth), regras, cenários e massas de dados. O JSON é versionado
  (`testflow_export_version`), para permitir evoluir o formato no futuro sem quebrar arquivos antigos.
- **Segredos nunca são exportados** — nem mascarados: token, senha e API key de autenticação são
  **omitidos por completo** do arquivo (`_strip_auth_secrets` em `app/api/export_import.py`), assim
  como qualquer header sensível. Só metadados sobrevivem (tipo de auth, nome do header, usuário).
- **Importação** (`POST /api/projects/import`) sempre cria um **projeto novo** — nunca sobrescreve um
  projeto existente. Requisições que precisavam de segredos removidos aparecem destacadas como
  "precisam de autenticação" — você reconfigura o segredo manualmente em "Editar API" depois de importar.

---

## 14. pytest como motor de execução

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

## 15. Como interpretar o dashboard

Depois da execução você é levado para a tela de resultado:

- **Cartões de resumo**: total de testes, 🟢 passed, 🔴 failed, ⚪ skipped, duração — vêm diretamente do relatório do pytest, não de uma contagem própria do backend.
- **Lista de testes**: cada linha é clicável.
- **Detalhe do teste**: mostra **Expected** vs **Actual** lado a lado (a comparação central do spec original), a mensagem bruta do pytest, o **request efetivamente enviado** naquela execução (`request-viewer`, a partir do `sent_request_snapshot` gravado em `Execution` — inclui as variáveis resolvidas quando veio de um cenário ou de uma massa de dados), e — se o teste falhou — um painel **"🤖 AI ANALYSIS"** com um botão para pedir à IA uma explicação da falha e possíveis próximos passos de investigação. A IA só explica; ela nunca decide se o teste passou.
- **📜 Histórico**: todas as execuções anteriores daquela API, com data, passed/failed/duração — clique em "ver detalhes" para reabrir qualquer execução passada. Execuções disparadas por uma massa de dados aparecem agrupadas sob a `BatchExecution` correspondente (seção 11).

---

## 16. Segurança

- Tokens, senhas e API keys são **criptografados** (Fernet/AES simétrico, `app/core/security.py`) antes de ir para o SQLite — nunca em texto puro.
- A chave de criptografia é gerada automaticamente na primeira execução (`backend/.secret_key`, fora do controle de versão) ou pode vir de `API_TESTFLOW_SECRET_KEY` / `API_TESTFLOW_SECRET_KEY_FILE`.
- Na interface e em qualquer payload enviado a um provider de IA, segredos aparecem **mascarados** (`Bearer eyJhbG...********`) — centralizado em `app/ai/context.py`.
- **Exportar projeto** (seção 13) nunca inclui segredos de autenticação, nem mascarados — eles são omitidos por completo do arquivo exportado.
- Mensagens de erro voltadas ao usuário (status HTTP, falha de conexão, erro interno, erro de validação) passam por `app/core/error_messages.py`, que também tem a responsabilidade de nunca vazar segredos (`token=`, `password=`, `api_key=`, querystrings) nem stack traces para a resposta HTTP ou para o cliente.
- Operações que alteram dados (POST/PUT/PATCH/DELETE) exigem confirmação explícita (`confirm=true`) tanto para "Testar API" quanto para "Executar testes" (incluindo execução de cenário e de massa de dados) — a IA sugerindo um cenário negativo mutante nunca dispara a chamada sozinha.
- **Atenção**: `app/engine/http_executor.py` chama o cliente `httpx` com `verify=False`, ou seja, a verificação de certificado TLS está **desativada** para toda chamada de teste feita pela plataforma (provavelmente para permitir testar APIs internas/self-signed sem fricção). Isso não está documentado em nenhum lugar do código-fonte além deste README — se você for testar APIs sensíveis pela rede pública, esteja ciente de que um ataque man-in-the-middle não seria detectado pela ferramenta.

---

## 17. Como adicionar novas validações (operadores)

Todo operador vive em **um único lugar**: `backend/app/engine/evaluator.py`, função `evaluate_check`. Para adicionar um operador novo (ex: `is_uuid_format`):

1. Adicione um `if operator == "is_uuid_format": ...` em `evaluate_check`, retornando um `EvalResult(passed, actual, expected, message)`.
2. Adicione a opção em `frontend/src/app/core/models/index.ts` (`OPERATORS`).
3. (Opcional) Adicione um teste em `backend/tests/test_evaluator.py`.

Como `test_rules.py` (o teste pytest real) e a pré-visualização da UI usam a **mesma** função, o novo operador funciona nos dois lugares automaticamente.

Para adicionar uma nova validação **automática** (descoberta), edite `backend/app/engine/discovery.py` — lembre-se da regra de ouro da seção 9: só adicione checks que sejam fatos técnicos observáveis, nunca valores de negócio.

---

## 18. Como adicionar novos AI providers

1. Crie uma classe em `backend/app/ai/` implementando `AIProvider` (`app/ai/base.py`): `suggest_from_response`, `suggest_negative_cases`, `nl_to_rules`, `chat`, `suggest_test_data`, `answer_question`, `explain_failure`.
2. Registre-a em `app/ai/factory.py` (`get_ai_provider`), associando a um valor de `API_TESTFLOW_AI_PROVIDER`.
3. Nunca envie segredos não mascarados para um serviço externo, e documente claramente se o provider depende de rede/serviço pago — o padrão da plataforma é funcionar 100% offline e gratuita.
4. Siga o padrão de `openai_provider.py`: envolva o `HeuristicAIProvider` como fallback interno e capture qualquer exceção do provider externo, retornando o resultado heurístico em vez de propagar o erro — isso é o que garante que a ausência/falha de um provider de nuvem nunca derruba a plataforma.

---

## 19. Testes do próprio projeto

```bash
cd backend
pytest -q          # 200+ testes: evaluator, discovery, cURL, Bruno, CSV, templating,
                    # export/import, IA heurística (incluindo chat) e provider OpenAI
ruff check app tests
```

```bash
cd frontend
npm run build       # ng build (type-check + build de produção)
npm test            # jest (testes unitários dos componentes Angular)
```

---

## 20. Limitações conhecidas e próximos passos

Documentadas aqui de propósito, para não passar a impressão de que foram esquecidas:

- **Sem migrações de schema** (Alembic): mudanças no modelo exigem recriar o SQLite em dev. Aceitável para o estágio atual do projeto; adicionar Alembic é o próximo passo natural antes de um uso multiusuário sério.
- **Import de Bruno** cobre uma requisição por vez, não collections completas com environments (ver seção 8).
- **Cenários negativos sugeridos pela IA continuam sendo texto informativo** (título, descrição, status esperado) — a IA não converte automaticamente uma sugestão em um `Scenario` executável. A criação/execução de uma variação real da requisição agora é possível (seção 12, "Cenários"), mas continua sendo um passo manual: você lê a sugestão da IA e recria as variáveis à mão em um cenário.
- **`verify=False` no cliente HTTP** (seção 16): a verificação de certificado TLS está desativada para todas as chamadas de teste — revisar se isso deveria ser configurável antes de usar a ferramenta contra APIs sensíveis fora de uma rede confiável.
- **Sem autenticação de usuário/multi-tenant**: adequado para um time rodando localmente ou em um ambiente interno confiável, não para expor publicamente sem uma camada de auth na frente.
- **Regras condicionais sobre listas** (`array_path`/`condition_*`) hoje suportam uma única condição de filtro por regra, com `condition_operator` tipicamente `equals`. Condições compostas ("PREMIUM E ativo há mais de 1 ano") exigiriam encadear múltiplas regras ou um novo operador lógico — não implementado ainda.
- A detecção de condição pela IA heurística exige que o valor mencionado apareça **literalmente** (case-insensitive) em algum campo de algum item do array na resposta real observada; sinônimos/variações do valor (ex: "clientes premium" quando a API usa `"tier": "P"`) não são inferidos.
- **Chat da IA sem memória persistida**: cada pergunta no chat é respondida isoladamente com o contexto da requisição atual — não há histórico de conversa salvo no backend entre sessões.
- **Docker do frontend**: `docker-compose.yml` ainda define um serviço `frontend`, mas `frontend/Dockerfile`/`nginx.conf` não existem no repositório desde a migração para Angular — só o `backend` builda via Docker hoje (ver `README_SETUP.md`, seção 11).
