"""Roteador FastAPI para recepcao e extracao de documentos DANFE.

Disponibiliza o endpoint principal para recebimento de arquivos via upload (multiformat),
catálogo de modelos de IA disponíveis, consulta de métricas de consumo e
orquestracao com os modelos de Inteligencia Artificial selecionados.
Todos os endpoints protegidos utilizam autenticacao JWT e rate limiting.
"""

import time
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from App.Core.Config import configuracao
from App.Core.Dependencias import aplicar_rate_limit
from App.Core.GerenciadorMetricas import obter_consumo_cliente, registrar_consumo
from App.Schemas.AuthSchema import DadosCliente
from App.Schemas.DanfeSchema import (
    MetadadosProcessamento,
    RespostaConsumoCliente,
    RespostaExtracaoDANFE,
    RespostaModelosDisponiveis,
    ResumoConsumoPorModelo,
)
from App.Services.ExtractorFactory import ExtratorFabrica
from App.Services.ValidadorDocumentoService import ValidadorDocumentoService

roteador_danfe = APIRouter(prefix="/api/v1/danfe", tags=["DANFE Extrator"])

EXTENSOES_PERMITIDAS = {"pdf", "png", "jpg", "jpeg", "webp"}


@roteador_danfe.get(
    "/modelos",
    response_model=RespostaModelosDisponiveis,
    status_code=status.HTTP_200_OK,
    summary="Listar modelos de IA disponíveis",
    description="Retorna todos os modelos de IA suportados pela API, indicando quais estão ativos (com credenciais válidas) e qual é o modelo padrão sugerido."
)
async def listar_modelos_disponiveis() -> RespostaModelosDisponiveis:
    """Endpoint para consulta dos modelos de IA integrados à plataforma.

    Returns:
        RespostaModelosDisponiveis: Lista dos modelos, status de ativação e modelo padrão sugerido.
    """
    modelos = ExtratorFabrica.listar_modelos()
    total_ativos = sum(1 for m in modelos if m.ativo)
    modelo_padrao = ExtratorFabrica.obter_modelo_padrao()

    return RespostaModelosDisponiveis(
        modelo_padrao=modelo_padrao,
        total_modelos=len(modelos),
        total_ativos=total_ativos,
        modelos=modelos
    )


@roteador_danfe.get(
    "/consumo",
    response_model=RespostaConsumoCliente,
    status_code=status.HTTP_200_OK,
    summary="Consultar métricas de consumo do cliente",
    description="Retorna o histórico de uso e quantidade de requisições realizadas pelo cliente autenticado agrupadas por modelo e rota."
)
async def consultar_consumo_proprio(
    cliente: DadosCliente = Depends(aplicar_rate_limit)
) -> RespostaConsumoCliente:
    """Retorna o consolidado de uso do cliente autenticado via JWT.

    Args:
        cliente (DadosCliente): Dados do cliente autenticado.

    Returns:
        RespostaConsumoCliente: Métricas de uso agrupadas por modelo e rota.
    """
    consumo = obter_consumo_cliente(cliente.cliente_id)
    detalhes_modelos = [
        ResumoConsumoPorModelo(modelo_ia=k, total_requisicoes=v)
        for k, v in consumo.get("modelos", {}).items()
    ]

    return RespostaConsumoCliente(
        cliente_id=cliente.cliente_id,
        nome=cliente.nome,
        total_requisicoes=consumo.get("total_requisicoes", 0),
        consumo_por_modelo=detalhes_modelos,
        rotas=consumo.get("rotas", {})
    )


@roteador_danfe.post(
    "/extrair",
    response_model=RespostaExtracaoDANFE,
    status_code=status.HTTP_200_OK,
    summary="Extrai dados estruturados de uma NF/DANFE",
    description="Recebe um arquivo (PDF ou Imagem) e processa a extração de dados da NF através do modelo de IA selecionado, salvando o resultado em JSON na pasta Data/output."
)
async def extrair_danfe(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Arquivo da DANFE (PDF, PNG, JPG, WEBP)"),
    modelo_ia: str = Form("mistral", description="Modelo de IA a utilizar (gemini, openai, claude, groq, mistral, openrouter)"),
    cliente: DadosCliente = Depends(aplicar_rate_limit)
) -> RespostaExtracaoDANFE:
    """Endpoint HTTP para recebimento e processamento de documentos DANFE.

    Requer autenticacao JWT via header 'Authorization: Bearer <token>'.
    Rate limiting aplicado automaticamente por cliente.
    Aplica triagem rápida local (Guarda de Tokens) antes de chamar o modelo de IA.

    Args:
        background_tasks (BackgroundTasks): Injetor de tarefas em background do FastAPI.
        file (UploadFile): Arquivo enviado pelo cliente no formulario multipart.
        modelo_ia (str): Identificador do modelo de IA desejado.
        cliente (DadosCliente): Dados do cliente autenticado.

    Returns:
        RespostaExtracaoDANFE: Resposta padronizada contendo sucesso, dados extraidos e metadados.

    Raises:
        HTTPException: Em caso de extensão inválida, modelo desativado, arquivo irrelevante ou erro de IA.
    """
    nome_arquivo = file.filename or "documento_danfe.pdf"
    print(f"\n[DEBUG ROUTER] Recebendo requisição para arquivo: {nome_arquivo}")
    print(f"[DEBUG ROUTER] Modelo IA escolhido: {modelo_ia}")

    # 1. Validação Prévia do Modelo de IA Solicitado (Bloqueio Rápido)
    ativo, motivo = ExtratorFabrica.modelo_esta_ativo(modelo_ia)
    if not ativo:
        modelos_ativos = [m.id for m in ExtratorFabrica.listar_modelos() if m.ativo]
        str_ativos = ", ".join(modelos_ativos) if modelos_ativos else "Nenhum modelo ativo no momento"
        print(f"[DEBUG ROUTER] Modelo '{modelo_ia}' rejeitado: {motivo}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível utilizar o modelo '{modelo_ia}'. {motivo} Modelos ativos disponíveis: {str_ativos}."
        )

    # 2. Validação da Extensão do Arquivo
    extensao = nome_arquivo.lower().split(".")[-1]
    if extensao not in EXTENSOES_PERMITIDAS:
        print(f"[DEBUG ROUTER] Extensão não permitida: {extensao}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de arquivo '.{extensao}' não suportado. Formatos aceitos: {', '.join(EXTENSOES_PERMITIDAS)}"
        )

    tempo_inicio = time.perf_counter()

    try:
        conteudo_bytes = await file.read()
        print(f"[DEBUG ROUTER] Arquivo lido. Tamanho: {len(conteudo_bytes)} bytes")

        # 3. Triagem Prévia do Documento e Guarda de Tokens (Zero Tokens Cost)
        ValidadorDocumentoService.validar_documento(conteudo_bytes, nome_arquivo)
        print(f"[DEBUG ROUTER] Documento validado com sucesso pela guarda de tokens.")

        # 4. Obtém o extrator configurado para o modelo informado via Factory Pattern
        print(f"[DEBUG ROUTER] Instanciando extrator...")
        extrator = ExtratorFabrica.obter_extrator(modelo_ia)
        print(f"[DEBUG ROUTER] Extrator instanciado: {extrator.__class__.__name__}")

        # 5. Realiza a extração dos dados da DANFE
        print(f"[DEBUG ROUTER] Iniciando extração na classe do extrator...")
        dados_extraidos = await extrator.extrair_dados(
            conteudo_arquivo=conteudo_bytes,
            nome_arquivo=nome_arquivo
        )
        print(f"[DEBUG ROUTER] Extração concluída. Salvando JSON...")

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

        # Agenda o registro de consumo em background para não atrasar a resposta
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
        print(f"[DEBUG ROUTER] Validação rejeitou a requisição: {str(erro_validacao)}")
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


