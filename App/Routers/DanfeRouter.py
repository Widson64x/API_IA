"""Roteador FastAPI para recepção e extração de documentos DANFE.

Disponibiliza o endpoint principal para recebimento de arquivos via upload (multiformat)
e orquestração com os modelos de Inteligência Artificial selecionados.
"""

import time
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from App.Schemas.DanfeSchema import MetadadosProcessamento, RespostaExtracaoDANFE
from App.Services.ExtractorFactory import ExtratorFabrica
from App.Services.XmlGeneratorService import ServidorGeracaoArquivos

roteador_danfe = APIRouter(prefix="/api/v1/danfe", tags=["DANFE Extrator"])

EXTENSOES_PERMITIDAS = {"pdf", "png", "jpg", "jpeg", "webp"}


@roteador_danfe.post(
    "/extrair",
    response_model=RespostaExtracaoDANFE,
    status_code=status.HTTP_200_OK,
    summary="Extrai dados estruturados de uma DANFE",
    description="Recebe um arquivo (PDF ou Imagem) e processa a extração de dados da DANFE através do modelo de IA selecionado, salvando os resultados em JSON e XML em Data/output."
)
async def extrair_danfe(
    file: UploadFile = File(..., description="Arquivo da DANFE (PDF, PNG, JPG, WEBP)"),
    modelo_ia: str = Form("gemini-flash", description="Modelo de IA a utilizar (gemini-flash, gpt-4o-mini, claude-3-5-sonnet, deepseek-chat)")
) -> RespostaExtracaoDANFE:
    """Endpoint HTTP para recebimento e processamento de documentos DANFE.

    Args:
        file (UploadFile): Arquivo enviado pelo cliente no formulário multipart.
        modelo_ia (str): Identificador do modelo de IA desejado. Padrão 'gemini-flash'.

    Returns:
        RespostaExtracaoDANFE: Resposta padronizada contendo sucesso, dados extraídos e metadados.

    Raises:
        HTTPException: Em caso de extensão inválida ou erro no processamento da IA.
    """
    nome_arquivo = file.filename or "documento_danfe.pdf"
    extensao = nome_arquivo.lower().split(".")[-1]

    if extensao not in EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de arquivo '.{extensao}' não suportado. Formatos aceitos: {', '.join(EXTENSOES_PERMITIDAS)}"
        )

    tempo_inicio = time.perf_counter()

    try:
        conteudo_bytes = await file.read()
        
        # Obtém o extrator configurado para o modelo informado via Factory Pattern
        extrator = ExtratorFabrica.obter_extrator(modelo_ia)
        
        # Realiza a extração dos dados da DANFE
        dados_extraidos = await extrator.extrair_dados(
            conteudo_arquivo=conteudo_bytes,
            nome_arquivo=nome_arquivo
        )

        # Salva automaticamente os arquivos JSON e XML formatados na pasta Data/output
        ServidorGeracaoArquivos.salvar_arquivos_saida(
            dados=dados_extraidos,
            nome_arquivo_original=nome_arquivo
        )

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
            mensagem="Dados da DANFE extraídos com sucesso.",
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
