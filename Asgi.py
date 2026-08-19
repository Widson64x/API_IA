"""Ponto de entrada ASGI da aplicação para execução em produção via Uvicorn."""

import os
import sys

# Garante que o diretório raiz esteja no PATH de importação
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from App.Main import app
from App.Core.Config import configuracao

if __name__ == "__main__":
    subrota = configuracao.ROOT_PATH_FORMATTED
    print("--> INICIANDO SERVIDOR ASGI (UVICORN) PARA A API IA")
    print(f"--> Endereço local: http://{configuracao.HOST}:{configuracao.PORT}")
    print(f"--> Documentação:   http://{configuracao.HOST}:{configuracao.PORT}/docs")
    if subrota:
        print(f"--> Subrota Nginx:  {subrota}")
    
    uvicorn.run(
        "Asgi:app",
        host=configuracao.HOST,
        port=configuracao.PORT,
        reload=configuracao.DEBUG
    )
    
