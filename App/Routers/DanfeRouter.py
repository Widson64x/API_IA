"""Roteador FastAPI para recepcao e extracao de documentos DANFE.

Disponibiliza o endpoint principal para recebimento de arquivos via upload (multiformat)
e orquestracao com os modelos de Inteligencia Artificial selecionados.
Todos os endpoints sao protegidos por autenticacao JWT e rate limiting.
"""

import time
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from App.Core.Dependencias import aplicar_rate_limit
from App.Core.GerenciadorMetricas import registrar_consumo
from App.Schemas.AuthSchema import DadosCliente
from App.Schemas.DanfeSchema import MetadadosProcessamento, RespostaExtracaoDANFE
from App.Core.Config import configuracao
from App.Services.ExtractorFactory import ExtratorFabrica
from pathlib import Path

roteador_danfe = APIRouter(prefix="/api/v1/danfe", tags=["DANFE Extrator"])

EXTENSOES_PERMITIDAS = {"pdf", "png", "jpg", "jpeg", "webp"}


@roteador_danfe.post(
    "/extrair",
    response_model=RespostaExtracaoDANFE,
    status_code=status.HTTP_200_OK,
    summary="Extrai dados estruturados de uma NF/DANFE",
    description="Recebe um arquivo (PDF ou Imagem) e processa a extracao de dados da NF atraves do modelo de IA selecionado, salvando o resultado em JSON na pasta Data/output."
)
async def extrair_danfe(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Arquivo da DANFE (PDF, PNG, JPG, WEBP)"),
    modelo_ia: str = Form("gemini-flash", description="Modelo de IA a utilizar (gemini-flash, gpt-4o-mini, claude-3-5-sonnet, deepseek-chat)"),
    cliente: DadosCliente = Depends(aplicar_rate_limit)
) -> RespostaExtracaoDANFE:
    """Endpoint HTTP para recebimento e processamento de documentos DANFE.

    Requer autenticacao JWT via header 'Authorization: Bearer <token>'.
    Rate limiting aplicado automaticamente por cliente.

    Args:
        background_tasks (BackgroundTasks): Injetor de tarefas em background do FastAPI.
        file (UploadFile): Arquivo enviado pelo cliente no formulario multipart.
        modelo_ia (str): Identificador do modelo de IA desejado. Padrao 'gemini-flash'.
        cliente (DadosCliente): Dados do cliente autenticado (injetado via dependency).

    Returns:
        RespostaExtracaoDANFE: Resposta padronizada contendo sucesso, dados extraidos e metadados.

    Raises:
        HTTPException: Em caso de extensao invalida ou erro no processamento da IA.
    """
    nome_arquivo = file.filename or "documento_danfe.pdf"
    extensao = nome_arquivo.lower().split(".")[-1]

    if extensao not in EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de arquivo '.{extensao}' nao suportado. Formatos aceitos: {', '.join(EXTENSOES_PERMITIDAS)}"
        )

    tempo_inicio = time.perf_counter()

    try:
        conteudo_bytes = await file.read()
        
        # Obtem o extrator configurado para o modelo informado via Factory Pattern
        extrator = ExtratorFabrica.obter_extrator(modelo_ia)
        
        # Realiza a extracao dos dados da DANFE
        dados_extraidos = await extrator.extrair_dados(
            conteudo_arquivo=conteudo_bytes,
            nome_arquivo=nome_arquivo
        )

        # Salva automaticamente o arquivo JSON formatado na pasta Data/output
        configuracao.DIR_OUTPUT.mkdir(parents=True, exist_ok=True)
        nome_base = Path(nome_arquivo).stem
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

        # Agenda o registro de consumo em background para nao atrasar a resposta
        background_tasks.add_task(
            registrar_consumo,
            cliente_id=cliente.cliente_id,
            rota="/api/v1/danfe/extrair",
            modelo_ia=modelo_ia
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro interno durante o processamento da IA: {str(erro_interno)}"
        )

