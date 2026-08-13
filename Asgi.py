"""Ponto de entrada ASGI da aplicação para execução em produção via Uvicorn."""

import os
import sys

# Garante que o diretório raiz esteja no PATH de importação
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from App.Main import app
from App.Core.Config import configuracao

if __name__ == "__main__":
    print("--> INICIANDO SERVIDOR ASGI (UVICORN) PARA A API IA")
    print(f"--> Endereço: http://{configuracao.HOST}:{configuracao.PORT}")
    
    uvicorn.run(
        "Asgi:app",
        host=configuracao.HOST,
        port=configuracao.PORT,
        reload=configuracao.DEBUG
    )
