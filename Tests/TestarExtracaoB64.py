"""Script de teste para validar o endpoint de extração DANFE via Base64.

Testa o endpoint POST /api/v1/danfe/extrair-b64 utilizando arquivos reais
da pasta Data/input codificados em Base64 e valida a estrutura da resposta JSON.
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Optional

# Adiciona a raiz do projeto ao sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from App.Main import app
from App.Core.Config import configuracao

URL_API_PADRAO = "http://localhost:8000/api/v1/danfe/extrair-b64"
PASTA_INPUT_PADRAO = ROOT_DIR / "Data" / "input"


def obter_token_jwt_teste() -> str:
    """Gera um cliente de teste temporário e retorna um access token JWT válido."""
    with TestClient(app) as client:
        # Cria ou obtém API Key via rota admin
        headers_admin = {"x-admin-key": configuracao.ADMIN_API_KEY}
        resp_cliente = client.post(
            "/api/v1/admin/clientes",
            json={"nome": "Cliente Teste Automatizado Base64", "descricao": "Teste de integracao b64"},
            headers=headers_admin
        )
        if resp_cliente.status_code != 201:
            raise RuntimeError(f"Falha ao criar cliente de teste: {resp_cliente.text}")
        api_key = resp_cliente.json()["api_key"]

        # Troca a API key pelo token JWT
        resp_token = client.post("/api/v1/auth/token", json={"api_key": api_key})
        if resp_token.status_code != 200:
            raise RuntimeError(f"Falha ao obter token JWT: {resp_token.text}")
        return resp_token.json()["access_token"]


def codificar_arquivo_para_b64(caminho_arquivo: Path) -> str:
    """Lê um arquivo local e retorna seu conteúdo como string base64."""
    with open(caminho_arquivo, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def testar_extracao_b64_testclient(
    caminho_arquivo: Path,
    modelo_ia: str = "gemini"
) -> bool:
    """Testa diretamente contra a aplicação FastAPI usando TestClient com autenticação JWT."""
    if not caminho_arquivo.exists():
        print(f"[ERRO] Arquivo não encontrado: {caminho_arquivo}")
        return False

    tipo_arquivo = caminho_arquivo.suffix.lstrip(".").lower()
    print(f"\n-> Obtendo Token JWT de autenticação...")
    token = obter_token_jwt_teste()

    print(f"-> Codificando arquivo: {caminho_arquivo.name} ({caminho_arquivo.stat().st_size / 1024:.1f} KB)...")
    arquivo_b64 = codificar_arquivo_para_b64(caminho_arquivo)

    payload = {
        "tipo_arquivo": tipo_arquivo,
        "arquivo_b64": arquivo_b64,
        "modelo_ia": modelo_ia,
        "nome_arquivo": caminho_arquivo.name
    }

    print(f"-> Executando requisição autenticada via TestClient (POST /api/v1/danfe/extrair-b64)")
    print(f"   Modelo IA: {modelo_ia} | Tipo: {tipo_arquivo}")

    headers = {"Authorization": f"Bearer {token}"}
    tempo_inicio = time.perf_counter()
    with TestClient(app) as client:
        resposta = client.post("/api/v1/danfe/extrair-b64", json=payload, headers=headers)
    tempo_total = round(time.perf_counter() - tempo_inicio, 2)

    if resposta.status_code == 200:
        dados_resposta = resposta.json()
        sucesso = dados_resposta.get("sucesso", False)
        metadados = dados_resposta.get("metadados", {})
        dados_danfe = dados_resposta.get("dados", {})

        print(f"   [SUCESSO] Status: HTTP 200 | Tempo Total: {tempo_total}s | Tempo IA: {metadados.get('tempo_execucao_segundos')}s")
        print(f"   Provedor: {metadados.get('provedor')} | Modelo: {metadados.get('modelo_utilizado')}")
        print(f"   Total de notas extraídas: {dados_danfe.get('quantidade_nota', len(dados_danfe.get('notaFiscalList', [])))}")

        print("\n   Estrutura da Resposta:")
        print(json.dumps(dados_resposta, indent=2, ensure_ascii=False))
        return sucesso
    else:
        print(f"   [FALHA] Status: HTTP {resposta.status_code}")
        print(f"   Resposta: {resposta.text}")
        return False


def testar_extracao_b64_http(
    caminho_arquivo: Path,
    modelo_ia: str = "gemini",
    url_endpoint: str = URL_API_PADRAO
) -> bool:
    """Envia um arquivo codificado em base64 via HTTP para servidor rodando com token JWT."""
    import requests
    if not caminho_arquivo.exists():
        print(f"[ERRO] Arquivo não encontrado: {caminho_arquivo}")
        return False

    print(f"\n-> Obtendo Token JWT de autenticação...")
    token = obter_token_jwt_teste()

    tipo_arquivo = caminho_arquivo.suffix.lstrip(".").lower()
    arquivo_b64 = codificar_arquivo_para_b64(caminho_arquivo)

    payload = {
        "tipo_arquivo": tipo_arquivo,
        "arquivo_b64": arquivo_b64,
        "modelo_ia": modelo_ia,
        "nome_arquivo": caminho_arquivo.name
    }

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"-> Enviando requisição HTTP autenticada para: {url_endpoint}")
    tempo_inicio = time.perf_counter()
    try:
        resposta = requests.post(url_endpoint, json=payload, headers=headers, timeout=120)
        tempo_total = round(time.perf_counter() - tempo_inicio, 2)

        if resposta.status_code == 200:
            dados_resposta = resposta.json()
            sucesso = dados_resposta.get("sucesso", False)
            print(f"   [SUCESSO] Status: HTTP 200 | Tempo Total: {tempo_total}s")
            print(json.dumps(dados_resposta, indent=2, ensure_ascii=False))
            return sucesso
        else:
            print(f"   [FALHA] Status: HTTP {resposta.status_code} | Resposta: {resposta.text}")
            return False
    except Exception as e:
        print(f"[ERRO DE CONEXÃO/REQUISIÇÃO]: {str(e)}")
        return False


def executar():
    parser = argparse.ArgumentParser(description="Teste de Extração DANFE via Base64.")
    parser.add_argument("--arquivo", "-f", type=str, help="Caminho do arquivo para teste.")
    parser.add_argument("--modelo", "-m", type=str, default="mistral", help="Modelo de IA (gemini, openai, claude, etc.)")
    parser.add_argument("--http", action="store_true", help="Executa via HTTP contra o servidor local rodando.")
    args = parser.parse_args()

    print("=" * 70)
    print("TESTE DE EXTRAÇÃO DANFE VIA BASE64 (POST /api/v1/danfe/extrair-b64)")
    print("=" * 70)

    if args.arquivo:
        arquivo_selecionado = Path(args.arquivo)
    else:
        arquivos_pdf = list(PASTA_INPUT_PADRAO.glob("*.PDF")) + list(PASTA_INPUT_PADRAO.glob("*.pdf"))
        if not arquivos_pdf:
            print(f"[AVISO] Nenhum arquivo PDF encontrado em {PASTA_INPUT_PADRAO}")
            return
        arquivo_selecionado = arquivos_pdf[0]

    print(f"Arquivo selecionado para teste: {arquivo_selecionado.name}")

    if args.http:
        sucesso = testar_extracao_b64_http(arquivo_selecionado, modelo_ia=args.modelo)
    else:
        sucesso = testar_extracao_b64_testclient(arquivo_selecionado, modelo_ia=args.modelo)

    print("\n" + "=" * 70)
    print(f"RESULTADO: {'PASSOU' if sucesso else 'FALHOU'}")
    print("=" * 70)


if __name__ == "__main__":
    executar()
