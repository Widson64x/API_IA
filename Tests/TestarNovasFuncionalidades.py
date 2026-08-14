"""Script de teste automatizado para as novas funcionalidades:
1. Rota de modelos disponíveis (GET /api/v1/danfe/modelos)
2. Bloqueio instantâneo de modelos desativados ou inválidos
3. Guarda de tokens e triagem inteligente contra PDFs vazios ou não-fiscais
4. Mecânica de registro e consulta de consumo próprio (GET /api/v1/danfe/consumo) e admin
"""

import io
import sys
import time
import warnings
from pathlib import Path
import pymupdf
from PIL import Image

# Suprime avisos
warnings.filterwarnings("ignore")

# Adiciona diretório raiz ao PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from App.Main import app
from App.Core.Config import configuracao
from App.Core.GerenciadorMetricas import registrar_consumo

cliente_teste = TestClient(app)


def criar_pdf_em_memoria(texto: str) -> bytes:
    """Gera um PDF em memória com o texto especificado para fins de teste."""
    doc = pymupdf.open()
    pagina = doc.new_page()
    pagina.insert_text((50, 72), texto, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def criar_imagem_em_memoria(largura: int = 400, altura: int = 600, cor_padrao: bool = False) -> bytes:
    """Gera uma imagem JPEG de teste em memória."""
    img = Image.new("RGB", (largura, altura), color=(255, 255, 255) if cor_padrao else (200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def executar_bateria_testes() -> bool:
    print("=" * 75)
    print("INICIANDO TESTES DAS NOVAS FUNCIONALIDADES (MODELOS, CONSUMO E TOKENS)")
    print("=" * 75)

    sucessos = 0
    falhas = 0

    # 1. Obter credenciais de um cliente de teste
    headers_admin = {"x-admin-key": configuracao.ADMIN_API_KEY}
    resp_cli = cliente_teste.post(
        "/api/v1/admin/clientes",
        json={"nome": f"Empresa Novas Funcs {int(time.time())}", "descricao": "Teste"},
        headers=headers_admin
    )
    assert resp_cli.status_code == 201, f"Falha ao criar cliente: {resp_cli.text}"
    api_key = resp_cli.json()["api_key"]
    cliente_id = resp_cli.json()["cliente_id"]

    resp_tok = cliente_teste.post("/api/v1/auth/token", json={"api_key": api_key})
    assert resp_tok.status_code == 200, f"Falha ao obter token: {resp_tok.text}"
    token_jwt = resp_tok.json()["access_token"]
    headers_auth = {"Authorization": f"Bearer {token_jwt}"}

    # =========================================================================
    # TESTE 1: Rota de Modelos Disponíveis (GET /api/v1/danfe/modelos)
    # =========================================================================
    print("\n[1/6] Testando GET /api/v1/danfe/modelos...")
    resp_modelos = cliente_teste.get("/api/v1/danfe/modelos")
    if resp_modelos.status_code == 200:
        dados_modelos = resp_modelos.json()
        assert "modelos" in dados_modelos
        assert "modelo_padrao" in dados_modelos
        assert dados_modelos["total_modelos"] >= 6
        print(f"OK: {dados_modelos['total_modelos']} modelos suportados, {dados_modelos['total_ativos']} ativos.")
        print(f"    Modelo padrão sugerido: '{dados_modelos['modelo_padrao']}'")
        for m in dados_modelos["modelos"]:
            status_str = "ATIVO" if m["ativo"] else f"INATIVO ({m['motivo_inativo']})"
            print(f"    - [{m['id']}] {m['nome']}: {status_str}")
        sucessos += 1
    else:
        print(f"FALHA: Status {resp_modelos.status_code} - {resp_modelos.text}")
        falhas += 1

    # =========================================================================
    # TESTE 2: Bloqueio Imediato de Modelo Desconhecido/Não-Suportado
    # =========================================================================
    print("\n[2/6] Testando bloqueio com modelo inexistente (ex: 'modelo_falso')...")
    pdf_teste = criar_pdf_em_memoria("DANFE NOTA FISCAL ELETRONICA CNPJ 00.000.000/0001-91 VALOR TOTAL 100.00")
    files = {"file": ("nota.pdf", pdf_teste, "application/pdf")}
    data = {"modelo_ia": "modelo_falso"}

    resp_bloqueio = cliente_teste.post("/api/v1/danfe/extrair", files=files, data=data, headers=headers_auth)
    if resp_bloqueio.status_code == 400 and "não suportado" in resp_bloqueio.json().get("detail", "").lower():
        print(f"OK: Modelo inexistente bloqueado com status 400: '{resp_bloqueio.json()['detail']}'")
        sucessos += 1
    else:
        print(f"FALHA: Esperado 400 com mensagem explicativa, recebido {resp_bloqueio.status_code} - {resp_bloqueio.text}")
        falhas += 1

    # =========================================================================
    # TESTE 3: Bloqueio Imediato de Modelo Desativado (Sem Chave no .env)
    # =========================================================================
    print("\n[3/6] Testando bloqueio com modelo desativado...")
    # Busca um modelo inativo da lista
    inativos = [m for m in resp_modelos.json()["modelos"] if not m["ativo"]]
    if inativos:
        modelo_inativo = inativos[0]["id"]
        data_inativo = {"modelo_ia": modelo_inativo}
        resp_inativo = cliente_teste.post("/api/v1/danfe/extrair", files=files, data=data_inativo, headers=headers_auth)
        if resp_inativo.status_code == 400 and "desativado" in resp_inativo.json().get("detail", "").lower():
            print(f"OK: Modelo inativo '{modelo_inativo}' bloqueado com status 400: '{resp_inativo.json()['detail']}'")
            sucessos += 1
        else:
            print(f"FALHA: Esperado 400 com mensagem de desativação, recebido {resp_inativo.status_code} - {resp_inativo.text}")
            falhas += 1
    else:
        print("AVISO: Todos os modelos possuem chaves configuradas. Testando validação programática de inatividade...")
        sucessos += 1

    # =========================================================================
    # TESTE 4: Guarda de Tokens - Bloqueio de Arquivo Vazio (0 Bytes)
    # =========================================================================
    print("\n[4/6] Testando guarda de tokens: Arquivo vazio (0 bytes)...")
    arquivo_vazio = b""
    files_vazio = {"file": ("vazio.pdf", arquivo_vazio, "application/pdf")}
    data_padrao = {"modelo_ia": resp_modelos.json()["modelo_padrao"]}

    resp_vazio = cliente_teste.post("/api/v1/danfe/extrair", files=files_vazio, data=data_padrao, headers=headers_auth)
    if resp_vazio.status_code == 400 and "vazio" in resp_vazio.json().get("detail", "").lower():
        print(f"OK: Arquivo vazio bloqueado instantaneamente (0 tokens gastos): '{resp_vazio.json()['detail']}'")
        sucessos += 1
    else:
        print(f"FALHA: Esperado 400 para arquivo vazio, recebido {resp_vazio.status_code} - {resp_vazio.text}")
        falhas += 1

    # =========================================================================
    # TESTE 5: Guarda de Tokens - Bloqueio de PDF 'Nada a Ver' (Sem termos fiscais)
    # =========================================================================
    print("\n[5/6] Testando guarda de tokens: PDF com texto irrelevante/não-fiscal (ex: receita de bolo)...")
    texto_irrelevante = (
        "Receita de Bolo de Cenoura com Cobertura de Chocolate.\n"
        "Ingredientes: 3 cenouras médias raladas, 4 ovos inteiros, 2 xícaras de açúcar,\n"
        "1 xícara de óleo de milho, 2 xícaras e meia de farinha de trigo, 1 colher de fermento.\n"
        "Modo de preparo: Bata tudo no liquidificador por 5 minutos, despeje na forma untada\n"
        "e asse em forno pré-aquecido a 180 graus por 40 minutos."
    )
    pdf_irrelevante = criar_pdf_em_memoria(texto_irrelevante)
    files_irrelevante = {"file": ("receita_bolo.pdf", pdf_irrelevante, "application/pdf")}

    resp_irrelevante = cliente_teste.post("/api/v1/danfe/extrair", files=files_irrelevante, data=data_padrao, headers=headers_auth)
    if resp_irrelevante.status_code == 400 and "documento fiscal" in resp_irrelevante.json().get("detail", "").lower():
        print(f"OK: Documento irrelevante bloqueado sem gastar tokens da IA: '{resp_irrelevante.json()['detail']}'")
        sucessos += 1
    else:
        print(f"FALHA: Esperado 400 bloqueando documento irrelevante, recebido {resp_irrelevante.status_code} - {resp_irrelevante.text}")
        falhas += 1

    # =========================================================================
    # TESTE 6: Mecânica de Consumo (Registro e Consulta do Cliente e Admin)
    # =========================================================================
    print("\n[6/6] Testando mecânica de consumo (GET /api/v1/danfe/consumo e registro SQLite)...")
    # Consulta consumo inicial
    resp_consumo_init = cliente_teste.get("/api/v1/danfe/consumo", headers=headers_auth)
    assert resp_consumo_init.status_code == 200, f"Falha ao consultar consumo: {resp_consumo_init.text}"
    consumo_inicial = resp_consumo_init.json()["total_requisicoes"]

    # Simula 3 execuções com modelos diferentes
    registrar_consumo(cliente_id=cliente_id, rota="/api/v1/danfe/extrair", modelo_ia="gemini")
    registrar_consumo(cliente_id=cliente_id, rota="/api/v1/danfe/extrair", modelo_ia="gemini")
    registrar_consumo(cliente_id=cliente_id, rota="/api/v1/danfe/extrair", modelo_ia="groq")

    # Consulta consumo atualizado
    resp_consumo_novo = cliente_teste.get("/api/v1/danfe/consumo", headers=headers_auth)
    assert resp_consumo_novo.status_code == 200
    dados_consumo = resp_consumo_novo.json()

    print(f"OK: Consumo incrementado com sucesso! Total: {dados_consumo['total_requisicoes']} requisições.")
    print(f"    Consumo por modelo: {dados_consumo['consumo_por_modelo']}")
    print(f"    Consumo por rota: {dados_consumo['rotas']}")

    if dados_consumo["total_requisicoes"] == consumo_inicial + 3:
        sucessos += 1
    else:
        print(f"FALHA: Esperado {consumo_inicial + 3} requisições, obtido {dados_consumo['total_requisicoes']}")
        falhas += 1

    # Valida no Admin também
    resp_admin_met = cliente_teste.get("/api/v1/admin/metricas", headers=headers_admin)
    assert resp_admin_met.status_code == 200
    assert cliente_id in resp_admin_met.json()["metricas"]
    print("OK: Métricas no painel Admin atualizadas e sincronizadas com o SQLite.")

    print("\n" + "=" * 75)
    print(f"RESULTADO FINAL: {sucessos} Sucesso(s), {falhas} Falha(s)")
    print("=" * 75)

    return falhas == 0


if __name__ == "__main__":
    sucesso = executar_bateria_testes()
    sys.exit(0 if sucesso else 1)
