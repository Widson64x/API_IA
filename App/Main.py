"""Ponto de entrada principal da API de Extracao de DANFE com IA.

Inicializa o servico FastAPI, configura os middleware de CORS,
registra os roteadores da aplicacao (DANFE, autenticacao e administracao)
e inicia o servidor Uvicorn.
"""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from App.Core.Config import configuracao
from App.Core.Database import inicializar_banco
from App.Routers.AdminRouter import roteador_admin
from App.Routers.AuthRouter import roteador_auth
from App.Routers.DanfeRouter import roteador_danfe

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicacao FastAPI (startup/shutdown)."""
    # Inicializa o banco de dados e cria as tabelas caso nao existam
    inicializar_banco()
    yield

# Instanciacao da aplicacao FastAPI
app = FastAPI(
    title="API de Extracao de DANFE com IA Multi-Provedor",
    description=(
        "API para recepcao de notas fiscais (DANFE em PDF/Imagem) e extracao de dados "
        "via Gemini, OpenAI, Claude e DeepSeek. Autenticacao via JWT com API Keys."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    root_path=configuracao.ROOT_PATH_FORMATTED,
    lifespan=lifespan
)

# Configuracao de CORS para permitir acesso por sistemas clientes e interfaces web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro dos roteadores de API
app.include_router(roteador_auth)
app.include_router(roteador_admin)
app.include_router(roteador_danfe)


@app.get("/", summary="Healthcheck da aplicacao")
def verificar_status_api() -> dict:
    """Retorna o status de operacao da API.

    Endpoint publico, sem necessidade de autenticacao.

    Returns:
        dict: Informacoes de status e mensagem de boas-vindas.
    """
    subrota = configuracao.ROOT_PATH_FORMATTED
    return {
        "status": "online",
        "aplicacao": "API de Extracao de DANFE",
        "versao": "1.1.0",
        "subrota": subrota if subrota else "/",
        "documentacao": f"{subrota}/docs",
        "autenticacao": f"JWT via {subrota}/api/v1/auth/token"
    }


if __name__ == "__main__":
    uvicorn.run(
        "App.Main:app",
        host=configuracao.HOST,
        port=configuracao.PORT,
        reload=configuracao.DEBUG
    )

