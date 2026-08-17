# API TestFlow — Setup

## Índice

- [1. O que é o projeto](#1-o-que-é-o-projeto)
- [2. Arquitetura](#2-arquitetura)
- [3. Tecnologias utilizadas](#3-tecnologias-utilizadas)
- [4. Pré-requisitos](#4-pré-requisitos)
- [5. Instalação do projeto](#5-instalação-do-projeto)
- [6. Variáveis de ambiente](#6-variáveis-de-ambiente)
- [7. Como executar](#7-como-executar)
- [8. Como testar](#8-como-testar)
- [9. IA](#9-ia)
- [10. Dependências externas](#10-dependências-externas)
- [11. Docker](#11-docker)
- [12. Git](#12-git)
- [13. Checklist para novo computador](#13-checklist-para-novo-computador)

---

## 1. O que é o projeto

**API TestFlow** é uma plataforma para testar APIs sem escrever código. Você informa uma URL (ou importa um cURL / arquivo `.bru` do Bruno), a plataforma chama a API de verdade, mostra a resposta real (status, headers, JSON), e permite montar regras de negócio ("o campo X deve ser igual a Y") — manualmente ou com ajuda de uma IA opcional (que também conversa em chat livre sobre a API). As regras viram testes reais executados pelo **pytest**, que decide PASS/FAIL/SKIPPED. A mesma requisição também pode ser reexecutada com variáveis diferentes via **cenários** ou em lote via **massas de dados (CSV)**, e projetos inteiros podem ser **exportados/importados** como JSON (sem segredos). Resultado: qualquer pessoa do time consegue validar contratos de API — inclusive com dados variados — sem escrever nenhuma linha de teste.

## 2. Arquitetura

**Frontend**
- Angular **18.2.14** (standalone components)
- Serve a interface web onde o usuário cria projetos, testa APIs, monta regras e vê resultados.

**Backend**
- Python **3.12** + **FastAPI 0.115.6**
- Expõe a API REST que faz as chamadas HTTP reais, guarda projetos/requisições/regras e roda os testes.

**Banco de dados**
- **SQLite** (via SQLModel 0.0.22), arquivo local `backend/api_testflow.db`
- Não precisa instalar nada — o arquivo é criado sozinho na primeira execução.

**Testes**
- **pytest 8.3.4** (+ `pytest-json-report`)
- É o motor real de execução: cada regra aprovada vira um teste pytest, rodado em subprocesso. PASS/FAIL/SKIPPED sempre vêm do pytest, nunca da IA.

**IA**
- Provedor padrão: **heurístico** — regras/heurísticas em Python puro, dentro do próprio backend, sem nenhuma API externa e sem custo.
- Provedor opcional: **OpenAI** (modelo `gpt-4o-mini` por padrão), só ativa se configurado explicitamente via `API_TESTFLOW_AI_PROVIDER=openai` + `OPENAI_API_KEY`. Se a chamada à OpenAI falhar por qualquer motivo, cai automaticamente para o provider heurístico.
- Para que serve: sugerir regras a partir de sintaxe técnica ou de um requisito em linguagem natural, sugerir cenários de valor (PASS/FAIL) para uma regra já criada, sugerir cenários negativos, gerar massas de dados de teste, responder perguntas em chat livre e explicar falhas — sempre como sugestão/leitura, nunca decide o resultado.

**Testes orientados a dados / cenários**
- `app/engine/templating.py` resolve placeholders `{{variavel}}` em requisições e regras.
- **Massas de dados**: importação de CSV (`app/engine/csv_import.py`) para rodar a mesma requisição várias vezes, uma por linha, agrupadas em uma `BatchExecution`.
- **Cenários**: conjuntos nomeados de variáveis, salvos e reexecutáveis com um clique, sem duplicar a requisição.

## 3. Tecnologias utilizadas

| Tecnologia | O que é | Para que usamos | Versão |
|---|---|---|---|
| Angular | Framework frontend | Interface web da aplicação | 18.2.14 |
| Node.js | Runtime JavaScript | Rodar/compilar o Angular | 18.19.1+ / 20.11.1+ / 22+ |
| npm | Gerenciador de pacotes JS | Instalar dependências do frontend | 10.x |
| TypeScript | Linguagem tipada sobre JS | Linguagem do frontend Angular | 5.5.4 |
| Tailwind CSS | Framework CSS utilitário | Estilo/identidade visual do frontend | 4.3.3 |
| Jest | Framework de testes JS | Testes automatizados do frontend | 29.7.0 |
| Python | Linguagem do backend | Rodar o backend FastAPI | 3.12 |
| FastAPI | Framework web Python | API REST do backend | 0.115.6 |
| Uvicorn | Servidor ASGI | Servir o FastAPI | 0.34.0 |
| SQLModel | ORM (SQLAlchemy + Pydantic) | Acesso ao banco SQLite | 0.0.22 |
| Pydantic | Validação de dados | Schemas de entrada/saída da API | 2.10.4 |
| httpx | Cliente HTTP Python | Fazer as chamadas reais às APIs testadas | 0.28.1 |
| pytest | Framework de testes Python | Motor real de execução (PASS/FAIL/SKIPPED) | 8.3.4 |
| cryptography | Criptografia | Criptografar tokens/senhas salvos (Fernet) | 44.0.0 |
| openai | SDK oficial da OpenAI | Provedor de IA opcional (LLM real em nuvem) | 1.109.1 |
| ruff | Linter Python | Checagem de qualidade do código backend | 0.8.4 |
| Docker | Containerização | Rodar o backend containerizado (ver seção 11) | — |
| Git / GitHub | Controle de versão | Versionar e hospedar o código | — |

## 4. Pré-requisitos

### Git

O que é: ferramenta de controle de versão.
Por que precisamos: para clonar e atualizar o projeto.
Versão: qualquer versão recente.
Verificar:
```
git --version
```
Instalar (Windows):
```
winget install Git.Git
```

### Node.js

O que é: runtime que executa o Angular CLI e compila o frontend.
Por que precisamos: sem ele não dá pra instalar nem rodar o Angular.
Versão: 18.19.1+, 20.11.1+ ou 22+ (exigido pelo `@angular/cli` 18 — testado com Node 20.19.2).
Verificar:
```
node --version
```
Instalar (Windows):
```
winget install OpenJS.NodeJS.LTS
```

### npm

O que é: gerenciador de pacotes que já vem junto com o Node.js.
Por que precisamos: instalar as dependências do frontend (`package.json`).
Versão: 10.x (vem com o Node LTS acima).
Verificar:
```
npm --version
```
Instalar: não precisa — já vem com o Node.js.

### Python

O que é: linguagem usada no backend.
Por que precisamos: rodar o FastAPI e o pytest.
Versão: 3.12.
Verificar:
```
python --version
```
Instalar (Windows):
```
winget install Python.Python.3.12
```

### Docker Desktop (opcional)

O que é: ferramenta para rodar aplicações em containers.
Por que precisamos: só se você quiser rodar o **backend** sem instalar Python direto na máquina (ver seção 11 — hoje o frontend não builda via Docker).
Versão: qualquer versão recente do Docker Desktop.
Verificar:
```
docker --version
```
Instalar (Windows):
```
winget install Docker.DockerDesktop
```

## 5. Instalação do projeto

```bash
git clone https://github.com/AngelicaDias-tech/api-testflow.git
cd api-testflow
```

**Backend — criar ambiente virtual e instalar dependências:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (cmd/PowerShell)
# source .venv/Scripts/activate   # Git Bash no Windows
pip install -r requirements.txt
```

**Frontend — instalar dependências:**
```bash
cd ../frontend
npm install
```

Não existe passo de `.env` obrigatório: o backend funciona com os valores padrão (banco SQLite criado automaticamente, chave de criptografia gerada sozinha em `backend/.secret_key`, IA heurística sem configuração nenhuma). Só crie variáveis de ambiente se quiser mudar algum desses padrões (ver seção 6).

## 6. Variáveis de ambiente

Nenhuma é obrigatória para rodar localmente — todas têm um valor padrão seguro. Defina-as como variáveis de ambiente do sistema/terminal antes de subir o backend, se quiser sobrescrever algo.

```
API_TESTFLOW_DATABASE_URL=sqlite:///./api_testflow.db
```
Onde o banco SQLite é salvo. Padrão já funciona sem configurar nada.

```
API_TESTFLOW_AI_PROVIDER=heuristic
```
Qual provedor de IA usar: `heuristic` (padrão, sem dependência externa) ou `openai` (LLM real em nuvem).

```
OPENAI_API_KEY=
```
Chave de API da OpenAI. Obrigatória apenas se `API_TESTFLOW_AI_PROVIDER=openai`. Nunca coloque uma chave real em texto no repositório.

```
API_TESTFLOW_OPENAI_MODEL=gpt-4o-mini
```
Nome do modelo da OpenAI a ser usado. Só é usado se `API_TESTFLOW_AI_PROVIDER=openai`.

```
API_TESTFLOW_OPENAI_TIMEOUT=60
```
Tempo máximo (segundos) para aguardar resposta da OpenAI antes de cair para o provider heurístico. Só é usado se `API_TESTFLOW_AI_PROVIDER=openai`.

```
API_TESTFLOW_SECRET_KEY=
```
Chave usada para criptografar tokens/senhas salvos no banco. Se não for definida, o backend gera e guarda uma automaticamente em `backend/.secret_key` — não precisa configurar em ambiente local. **Nunca coloque uma chave real em texto no repositório.**

```
API_TESTFLOW_HTTP_TIMEOUT=15
```
Tempo máximo (segundos) que uma chamada de teste pode levar.

```
API_TESTFLOW_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```
Origens que o backend aceita receber chamadas. **Atenção:** o padrão ainda lista a porta antiga do Vite/React (5173), não a porta do Angular (4200). Isso não atrapalha rodar com `ng serve` (o Angular faz proxy interno para o backend, então o navegador não chama a porta 8000 diretamente), mas se você for expor o frontend de outra forma, atualize essa variável para incluir `http://localhost:4200`.

## 7. Como executar

### Backend

```bash
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```
Fica disponível em **http://localhost:8000** (documentação automática em `http://localhost:8000/docs`).

### Frontend Angular

```bash
cd frontend
npm start
```
Fica disponível em **http://localhost:4200**. As chamadas para `/api/*` são automaticamente redirecionadas para o backend (configurado em `frontend/proxy.conf.json`) — por isso o backend precisa estar rodando antes.

## 8. Como testar

1. Suba o backend (seção 7).
2. Suba o frontend (seção 7).
3. Abra `http://localhost:4200` no navegador.
4. Crie um projeto (botão "+ Criar projeto").
5. Dentro do projeto, clique em "🚀 Testar nova API", informe uma URL e clique em "🚀 TESTAR API".
6. Adicione pelo menos uma regra (manual, na seção "🎯 Regras de Negócio") e clique em "▶ Executar testes".
7. Confirme que a tela de resultado mostra PASS/FAIL/SKIPPED reais.
8. (Opcional) Teste os recursos novos: aba "📊 Massas de dados" (importar um CSV e rodar a requisição em lote), aba "🧪 Cenários" (salvar um conjunto de variáveis e reexecutar), e o botão "📤 exportar" na tela de projetos.

**Testes automatizados do próprio projeto:**
```bash
# Backend
cd backend && pytest -q

# Frontend
cd frontend && npm test
```

## 9. IA

- **Modelo/provedor usado por padrão:** nenhum modelo de nuvem — um provedor **heurístico** (`HeuristicAIProvider`, `backend/app/ai/heuristic_provider.py`), regras Python que rodam localmente, sem chamada externa e sem custo.
- **Provedor opcional:** OpenAI (`backend/app/ai/openai_provider.py`), que fala com a API da OpenAI (modelo `gpt-4o-mini` por padrão) via o SDK oficial `openai`. Só é ativado com `API_TESTFLOW_AI_PROVIDER=openai` e `OPENAI_API_KEY` configurada.
- **Biblioteca/SDK de comunicação:** nenhum SDK de IA para o provedor heurístico (não faz chamada nenhuma); o provedor OpenAI usa o SDK oficial `openai` (dependência do projeto).
- **Onde fica a configuração:** `backend/app/core/config.py` (lê as variáveis `API_TESTFLOW_AI_PROVIDER`, `OPENAI_API_KEY`, `API_TESTFLOW_OPENAI_MODEL`, `API_TESTFLOW_OPENAI_TIMEOUT`) e `backend/app/ai/factory.py` (decide qual provedor instanciar).
- **Funcionalidades que usam IA:** "Gerar regras" (sintaxe técnica → regra estruturada), "Analisar requisito" (linguagem natural livre → regra estruturada), "Sugerir cenários" (valores de exemplo PASS/FAIL para uma regra já aprovada), sugestão de cenários negativos, geração de massa de dados de teste, chat livre sobre a requisição/resposta, explicação de falha de teste.
- **Funcionalidades que NÃO dependem de IA:** criar/testar API, ver resposta real (JSON/headers/status) e o request enviado, construtor manual de regras de negócio, cenários manuais, massas de dados via CSV, exportar/importar projeto, execução dos testes via pytest, PASS/FAIL/SKIPPED, histórico de execuções — tudo isso funciona 100% sem a IA disponível.

## 10. Dependências externas

**A API que você decide testar** (ex.: `https://api.github.com/...`)
Para que serve: é o alvo dos testes — o próprio objetivo da ferramenta.
Precisa de token? Só se a API que você for testar exigir (você configura isso na tela de criação da requisição).
É obrigatório? Sim, é o uso central da ferramenta.
Onde configurar? Direto na interface, ao criar/editar uma requisição.

**OpenAI** (opcional)
Para que serve: rodar um modelo de IA real (LLM em nuvem) mais sofisticado que o heurístico padrão.
Precisa de token? Sim, `OPENAI_API_KEY`.
É obrigatório? Não — o projeto funciona completo sem ele.
Onde configurar? Variáveis `API_TESTFLOW_AI_PROVIDER=openai`, `OPENAI_API_KEY`, `API_TESTFLOW_OPENAI_MODEL` (seção 6).

Nenhum outro serviço externo (nenhuma API de IA paga, nenhum banco de dados externo) é necessário.

## 11. Docker

O `docker-compose.yml` na raiz define dois serviços: `backend` (builda `backend/Dockerfile`, porta 8000) e `frontend` (tentaria buildar `frontend/Dockerfile`, porta 8080).

**Situação atual:** o serviço de **backend** funciona normalmente via Docker. O serviço de **frontend não funciona hoje** — `frontend/Dockerfile` e `frontend/nginx.conf` não existem mais no repositório (foram removidos quando o frontend migrou de React para Angular e ainda não foram recriados para o Angular). Rodar `docker compose up` vai falhar ao tentar buildar o frontend.

**Instalar Docker Desktop (Windows):**
```
winget install Docker.DockerDesktop
```

**Rodar só o backend via Docker (funciona hoje):**
```bash
docker build -t api-testflow-backend ./backend
docker run -p 8000:8000 -v api_testflow_data:/data api-testflow-backend
```

Para uso local do dia a dia, **não é necessário usar Docker** — rodar backend e frontend diretamente (seção 7) é o caminho recomendado e mais simples.

## 12. Git

- **Git**: ferramenta de controle de versão instalada na sua máquina.
- **GitHub**: onde o código deste projeto está hospedado (`https://github.com/AngelicaDias-tech/api-testflow`).

**Clonar:**
```bash
git clone https://github.com/AngelicaDias-tech/api-testflow.git
```

**Verificar em qual branch você está:**
```bash
git branch --show-current
```

**Atualizar o projeto com as últimas mudanças:**
```bash
git pull origin master
```

## 13. Checklist para novo computador

- [ ] Git instalado
- [ ] Node.js instalado (18.19.1+/20.11.1+/22+)
- [ ] npm funcionando
- [ ] Python instalado (3.12)
- [ ] Repositório clonado
- [ ] Dependências do backend instaladas (`pip install -r requirements.txt` dentro do venv)
- [ ] Dependências do frontend instaladas (`npm install`)
- [ ] Variáveis de ambiente revisadas (opcional — funciona sem configurar nada)
- [ ] Backend rodando em `http://localhost:8000`
- [ ] Angular rodando em `http://localhost:4200`
- [ ] IA configurada, se quiser usar OpenAI (opcional — funciona sem)
- [ ] Aplicação aberta no navegador
- [ ] Projeto criado, API testada e execução com PASS/FAIL confirmada
