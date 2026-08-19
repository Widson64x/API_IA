"""Roteador FastAPI para recepcao e extracao de documentos DANFE.

Disponibiliza o endpoint principal para recebimento de arquivos via upload (multiformat)
e orquestracao com os modelos de Inteligencia Artificial selecionados.
Todos os endpoints sao protegidos por autenticacao JWT e rate limiting.
"""

import base64
import time
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from App.Core.Dependencias import aplicar_rate_limit
from App.Core.GerenciadorMetricas import registrar_consumo
from App.Schemas.AuthSchema import DadosCliente
from App.Schemas.DanfeSchema import MetadadosProcessamento, RequisicaoExtracaoB64, RespostaExtracaoDANFE
from App.Core.Config import configuracao
from App.Services.ExtractorFactory import ExtratorFabrica
from pathlib import Path

roteador_danfe = APIRouter(prefix="/api/v1/danfe", tags=["DANFE Extrator"])

EXTENSOES_PERMITIDAS = {"pdf", "png", "jpg", "jpeg", "webp"}


async def _processar_extracao(
    conteudo_bytes: bytes,
    nome_arquivo: str,
    modelo_ia: str
) -> RespostaExtracaoDANFE:
    """Função auxiliar interna para executar a extração via IA e persistir a saída."""
    extensao = nome_arquivo.lower().split(".")[-1]

    if extensao not in EXTENSOES_PERMITIDAS:
        print(f"[DEBUG ROUTER] Extensão não permitida: {extensao}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de arquivo '.{extensao}' nao suportado. Formatos aceitos: {', '.join(EXTENSOES_PERMITIDAS)}"
        )

    tempo_inicio = time.perf_counter()

    try:
        print(f"[DEBUG ROUTER] Instanciando extrator...")
        extrator = ExtratorFabrica.obter_extrator(modelo_ia)
        print(f"[DEBUG ROUTER] Extrator instanciado: {extrator.__class__.__name__}")

        print(f"[DEBUG ROUTER] Iniciando extração na classe do extrator...")
        dados_extraidos = await extrator.extrair_dados(
            conteudo_arquivo=conteudo_bytes,
            nome_arquivo=nome_arquivo
        )
        print(f"[DEBUG ROUTER] Extração concluída. Preenchendo metadados do arquivo...")

        # Preenchimento automático dos metadados foi movido para o ExtratorBase
        nome_p = Path(nome_arquivo)

        configuracao.DIR_OUTPUT.mkdir(parents=True, exist_ok=True)
        nome_base = nome_p.stem
        caminho_json = configuracao.DIR_OUTPUT / f"{nome_base}.json"

        with open(caminho_json, "w", encoding="utf-8") as file_json:
            file_json.write(dados_extraidos.model_dump_json(indent=2))

        tempo_total = round(time.perf_counter() - tempo_inicio, 3)
        nome_provedor = extrator.__class__.__name__.replace("Extrator", "")

        metadados = MetadadosProcessamento(
            modelo_utilizado=modelo_ia,
            provedor=nome_provedor,
            tempo_execucao_segundos=tempo_total,
            nome_arquivo_original=nome_arquivo
        )

        return RespostaExtracaoDANFE(
            sucesso=True,
            mensagem="Dados da DANFE extraidos com sucesso.",
            dados=dados_extraidos,
            metadados=metadados
        )

    except ValueError as erro_validacao:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(erro_validacao)
        )
    except Exception as erro_interno:
        print(f"[DEBUG ROUTER] ERRO FATAL: {str(erro_interno)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro interno durante o processamento da IA: {str(erro_interno)}"
        )


@roteador_danfe.post(
    "/extrair",
    response_model=RespostaExtracaoDANFE,
    status_code=status.HTTP_200_OK,
    summary="Extrai dados estruturados de uma NF/DANFE via Upload",
    description="Recebe um arquivo multipart/form-data (PDF ou Imagem) e processa a extracao de dados da NF atraves do modelo de IA selecionado, salvando o resultado em JSON na pasta Data/output."
)
async def extrair_danfe(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Arquivo da DANFE (PDF, PNG, JPG, WEBP)"),
    modelo_ia: str = Form("gemini", description="Modelo de IA a utilizar (gemini, openai, claude, deepseek, mistral, etc.)"),
    cliente: DadosCliente = Depends(aplicar_rate_limit)
) -> RespostaExtracaoDANFE:
    """Endpoint HTTP para recebimento e processamento de documentos DANFE via Upload.

    Requer autenticacao JWT via header 'Authorization: Bearer <token>'.
    Rate limiting aplicado automaticamente por cliente.
    """
    nome_arquivo = file.filename or "documento_danfe.pdf"
    print(f"\n[DEBUG ROUTER] Recebendo requisição multipart para arquivo: {nome_arquivo} | Cliente: {cliente.nome}")
    print(f"[DEBUG ROUTER] Modelo IA escolhido: {modelo_ia}")

    conteudo_bytes = await file.read()
    print(f"[DEBUG ROUTER] Arquivo lido. Tamanho: {len(conteudo_bytes)} bytes")

    background_tasks.add_task(
        registrar_consumo,
        cliente_id=cliente.cliente_id,
        rota="/api/v1/danfe/extrair",
        modelo_ia=modelo_ia
    )

    return await _processar_extracao(
        conteudo_bytes=conteudo_bytes,
        nome_arquivo=nome_arquivo,
        modelo_ia=modelo_ia
    )


@roteador_danfe.post(
    "/extrair-b64",
    response_model=RespostaExtracaoDANFE,
    status_code=status.HTTP_200_OK,
    summary="Extrai dados estruturados de uma NF/DANFE via Base64",
    description="Recebe o tipo do arquivo e o conteudo em base64 (JSON payload) e processa a extracao de dados da NF atraves do modelo de IA selecionado."
)
async def extrair_danfe_b64(
    requisicao: RequisicaoExtracaoB64,
    background_tasks: BackgroundTasks,
    cliente: DadosCliente = Depends(aplicar_rate_limit)
) -> RespostaExtracaoDANFE:
    """Endpoint HTTP para processamento de DANFE enviada como Base64.

    Requer autenticacao JWT via header 'Authorization: Bearer <token>'.
    Rate limiting aplicado automaticamente por cliente.
    """
    tipo_limpo = requisicao.tipo_arquivo.strip().lower().lstrip(".")
    modelo_ia = requisicao.modelo_ia or "gemini"
    nome_arquivo = requisicao.nome_arquivo or f"documento_danfe.{tipo_limpo}"

    if not nome_arquivo.lower().endswith(f".{tipo_limpo}"):
        nome_arquivo = f"{Path(nome_arquivo).stem}.{tipo_limpo}"

    print(f"\n[DEBUG ROUTER] Recebendo requisição Base64. Tipo: {tipo_limpo}, Nome: {nome_arquivo} | Cliente: {cliente.nome}")
    print(f"[DEBUG ROUTER] Modelo IA escolhido: {modelo_ia}")

    # Remove possível prefixo Data URL (ex: 'data:application/pdf;base64,...')
    conteudo_b64 = requisicao.arquivo_b64
    if "," in conteudo_b64:
        conteudo_b64 = conteudo_b64.split(",", 1)[1]

    try:
        conteudo_bytes = base64.b64decode(conteudo_b64)
    except Exception as erro_b64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Conteúdo em base64 inválido: {str(erro_b64)}"
        )

    print(f"[DEBUG ROUTER] Base64 decodificado com sucesso. Tamanho: {len(conteudo_bytes)} bytes")

    background_tasks.add_task(
        registrar_consumo,
        cliente_id=cliente.cliente_id,
        rota="/api/v1/danfe/extrair-b64",
        modelo_ia=modelo_ia
    )

    return await _processar_extracao(
        conteudo_bytes=conteudo_bytes,
        nome_arquivo=nome_arquivo,
        modelo_ia=modelo_ia
    )

