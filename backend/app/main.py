from __future__ import annotations

import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import ai, datasets, executions, export_import, imports, projects, requests, rules, scenarios
from app.core.config import get_settings
from app.core.error_messages import internal_error_message, validation_error_message
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="API TestFlow",
    description="Plataforma universal de testes automatizados de APIs com pytest + IA",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(export_import.router)
app.include_router(imports.router)
app.include_router(requests.router)
app.include_router(rules.router)
app.include_router(executions.router)
app.include_router(executions.exec_router)
app.include_router(scenarios.router)
app.include_router(datasets.router)
app.include_router(datasets.batch_router)
app.include_router(ai.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Erro de validacao de payload (422) - mensagem amigavel e agregada em
    vez da lista bruta de erros do Pydantic, sem perder qual campo falhou
    (melhoria 1: 'erro de validacao')."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": validation_error_message(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Rede de seguranca final: qualquer excecao nao tratada por uma rota
    vira uma mensagem interna generica e amigavel (nunca uma stack trace
    crua) - o detalhe tecnico vai só para o console do servidor."""
    traceback.print_exc()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": internal_error_message()},
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}
