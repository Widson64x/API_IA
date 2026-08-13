"""Script de teste automatizado para validacao de todas as rotas de autenticacao e administracao.

Testa os fluxos de criacao de cliente, obtencao de tokens JWT, consulta de perfil,
renovacao de token, revogacao e desativacao de cliente.
Exclui propositalmente o endpoint de extracao DANFE para evitar consumo de tokens de IA.
"""

import sys
import warnings
from pathlib import Path

# Suprime avisos de deprecacao de bibliotecas de teste
warnings.filterwarnings("ignore")

# Adiciona o diretorio raiz ao PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from App.Main import app
from App.Core.Config import configuracao

cliente_teste = TestClient(app)


def executar_testes_autenticacao() -> bool:
    """Executa a bateria completa de testes de integracao dos endpoints.

    Returns:
        bool: True se todos os testes passaram com sucesso, False caso contrario.
    """
    print("=" * 70)
    print("INICIANDO VERIFICACAO COMPLETA DAS ROTAS DE AUTENTICACAO E ADMIN")
    print("=" * 70)

    sucessos = 0
    falhas = 0

    # 1. Teste Healthcheck (GET /)
    print("\n[1/8] Testando GET / (Healthcheck)...")
    resp = cliente_teste.get("/")
    if resp.status_code == 200 and resp.json().get("status") == "online":
        print("OK: Healthcheck online.")
        sucessos += 1
    else:
        print(f"FALHA: Status {resp.status_code} - {resp.text}")
        falhas += 1

    # 2. Teste Criar Cliente (POST /api/v1/admin/clientes)
    print("\n[2/8] Testando POST /api/v1/admin/clientes...")
    import time
    nome_cliente_teste = f"Empresa Teste {int(time.time())}"
    headers_admin = {"x-admin-key": configuracao.ADMIN_API_KEY}
    payload_cliente = {
        "nome": nome_cliente_teste,
        "descricao": "Cliente temporario para testes de integracao"
    }

    resp = cliente_teste.post("/api/v1/admin/clientes", json=payload_cliente, headers=headers_admin)

    if resp.status_code == 201:
        dados_resposta = resp.json()
        cliente_id = dados_resposta["cliente_id"]
        api_key = dados_resposta["api_key"]
        print(f"OK: Cliente criado com sucesso (ID: {cliente_id}).")
        sucessos += 1
    else:
        print(f"FALHA: Status {resp.status_code} - {resp.text}")
        falhas += 1
        return False

    # 3. Teste Listar Clientes (GET /api/v1/admin/clientes)
    print("\n[3/8] Testando GET /api/v1/admin/clientes...")
    resp = cliente_teste.get("/api/v1/admin/clientes", headers=headers_admin)
    if resp.status_code == 200 and resp.json().get("total", 0) > 0:
        print(f"OK: {resp.json()['total']} cliente(s) listado(s).")
        sucessos += 1
    else:
        print(f"FALHA: Status {resp.status_code} - {resp.text}")
        falhas += 1

    # 4. Teste Obter Token JWT via API Key (POST /api/v1/auth/token)
    print("\n[4/8] Testando POST /api/v1/auth/token...")
    resp = cliente_teste.post("/api/v1/auth/token", json={"api_key": api_key})
    if resp.status_code == 200:
        tokens = resp.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        print("OK: Access token e refresh token gerados com sucesso.")
        sucessos += 1
    else:
        print(f"FALHA: Status {resp.status_code} - {resp.text}")
        falhas += 1
        return False

    # 5. Teste Consultar Perfil com Access Token (GET /api/v1/auth/perfil)
    print("\n[5/8] Testando GET /api/v1/auth/perfil...")
    headers_bearer = {"Authorization": f"Bearer {access_token}"}
    resp = cliente_teste.get("/api/v1/auth/perfil", headers=headers_bearer)
    if resp.status_code == 200 and resp.json().get("cliente_id") == cliente_id:
        print(f"OK: Perfil autenticado para '{resp.json()['nome']}'.")
        sucessos += 1
    else:
        print(f"FALHA: Status {resp.status_code} - {resp.text}")
        falhas += 1

    # 6. Teste Renovar Token (POST /api/v1/auth/refresh)
    print("\n[6/8] Testando POST /api/v1/auth/refresh...")
    resp = cliente_teste.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    if resp.status_code == 200:
        novos_tokens = resp.json()
        novo_access = novos_tokens["access_token"]
        print("OK: Token renovado com sucesso.")
        sucessos += 1
    else:
        print(f"FALHA: Status {resp.status_code} - {resp.text}")
        falhas += 1

    # 7. Teste Revogar Token (POST /api/v1/auth/revogar)
    print("\n[7/8] Testando POST /api/v1/auth/revogar...")
    resp = cliente_teste.post("/api/v1/auth/revogar", json={"token": novo_access})
    if resp.status_code == 200 and resp.json().get("revogado") is True:
        print("OK: Token revogado com sucesso.")
        sucessos += 1
    else:
        print(f"FALHA: Status {resp.status_code} - {resp.text}")
        falhas += 1

    # Verificar que o token revogado nao funciona mais
    resp_rejeitada = cliente_teste.get("/api/v1/auth/perfil", headers={"Authorization": f"Bearer {novo_access}"})
    if resp_rejeitada.status_code == 401:
        print("OK: Token revogado foi rejeitado com HTTP 401 conforme esperado.")
    else:
        print(f"ALERTA: Esperado 401 para token revogado, recebido {resp_rejeitada.status_code}.")

    # 8. Teste Protecao de Autenticacao no Extrair (POST /api/v1/danfe/extrair sem token)
    print("\n[8/9] Testando POST /api/v1/danfe/extrair sem autenticacao...")
    resp_danfe_sem_auth = cliente_teste.post("/api/v1/danfe/extrair")
    if resp_danfe_sem_auth.status_code in (401, 403):
        print(f"OK: Endpoint /api/v1/danfe/extrair bloqueado sem token (HTTP {resp_danfe_sem_auth.status_code}).")
        sucessos += 1
    else:
        print(f"FALHA: Endpoint /api/v1/danfe/extrair permitiu acesso sem token! (Status {resp_danfe_sem_auth.status_code})")
        falhas += 1

    # 9. Teste Desativar Cliente (DELETE /api/v1/admin/clientes/{id})
    print(f"\n[9/9] Testando DELETE /api/v1/admin/clientes/{cliente_id}...")
    resp = cliente_teste.delete(f"/api/v1/admin/clientes/{cliente_id}", headers=headers_admin)
    if resp.status_code == 200 and resp.json().get("desativado") is True:
        print("OK: Cliente desativado com sucesso.")
        sucessos += 1
    else:
        print(f"FALHA: Status {resp.status_code} - {resp.text}")
        falhas += 1

    print("\n" + "=" * 70)
    print(f"RESULTADO DOS TESTES: {sucessos} Sucesso(s), {falhas} Falha(s)")
    print("=" * 70)

    return falhas == 0


if __name__ == "__main__":
    resultado_final = executar_testes_autenticacao()
    sys.exit(0 if resultado_final else 1)
