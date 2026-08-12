"""Ponto de entrada principal da API de Extração de DANFE com IA.

Inicializa o serviço FastAPI, configura os middleware de CORS,
registra os roteadores da aplicação e inicia o servidor Uvicorn.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from App.Core.Config import configuracao
from App.Routers.DanfeRouter import roteador_danfe

# Instanciação da aplicação FastAPI
app = FastAPI(
    title="API de Extração de DANFE com IA Multi-Provedor",
    description="API para recepção de notas fiscais (DANFE em PDF/Imagem) e extração de dados via Gemini, OpenAI, Claude e DeepSeek.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuração de CORS para permitir acesso por sistemas clientes e interfaces web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro dos roteadores de API
app.include_router(roteador_danfe)


@app.get("/", summary="Healthcheck da aplicação")
def verificar_status_api() -> dict:
    """Retorna o status de operação da API.

    Returns:
        dict: Informações de status e mensagem de boas-vindas.
    """
    return {
        "status": "online",
        "aplicacao": "API de Extração de DANFE",
        "versao": "1.0.0",
        "documentacao": "/docs"
    }


if __name__ == "__main__":
    uvicorn.run(
        "App.Main:app",
        host=configuracao.HOST,
        port=configuracao.PORT,
        reload=configuracao.DEBUG
    )
