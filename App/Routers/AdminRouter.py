"""Roteador FastAPI para endpoints administrativos de gestao de clientes.

Todos os endpoints deste router sao protegidos pela ADMIN_API_KEY
definida no .env. Apenas administradores podem registrar, listar
ou revogar clientes da API.
"""

from fastapi import APIRouter, Header, HTTPException, status

from App.Core.Config import configuracao
from App.Core.GerenciadorApiKeys import listar_clientes, registrar_cliente, revogar_cliente
from App.Core.GerenciadorMetricas import obter_metricas
from App.Schemas.AuthSchema import (
    RequisicaoRegistroCliente,
    RespostaListaClientes,
    RespostaRegistroCliente,
)

roteador_admin = APIRouter(prefix="/api/v1/admin", tags=["Administracao"])


def _validar_admin_key(x_admin_key: str = Header(..., description="Chave de administracao da API")) -> None:
    """Valida a chave administrativa enviada no header X-Admin-Key.

    Comparacao em tempo constante via hmac.compare_digest para
    prevenir timing attacks.

    Args:
        x_admin_key (str): Chave enviada no header da requisicao.

    Raises:
        HTTPException (403): Se a chave for invalida.
    """
    import hmac

    if not hmac.compare_digest(x_admin_key, configuracao.ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chave administrativa invalida. Acesso negado."
        )


@roteador_admin.post(
    "/clientes",
    response_model=RespostaRegistroCliente,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar novo cliente",
    description=(
        "Cria um novo cliente na API e gera uma API Key unica. "
        "A API Key e exibida APENAS nesta resposta — armazene-a com seguranca."
    )
)
async def criar_cliente(
    requisicao: RequisicaoRegistroCliente,
    x_admin_key: str = Header(..., description="Chave de administracao da API")
) -> RespostaRegistroCliente:
    """Registra um novo cliente e retorna a API Key gerada.

    Args:
        requisicao (RequisicaoRegistroCliente): Payload com nome e descricao do cliente.
        x_admin_key (str): Chave administrativa para autorizar a operacao.

    Returns:
        RespostaRegistroCliente: Dados do cliente criado, incluindo a API Key (unica exibicao).

    Raises:
        HTTPException (403): Se a chave administrativa for invalida.
        HTTPException (409): Se ja existir um cliente com o mesmo nome.
    """
    _validar_admin_key(x_admin_key)

    try:
        resultado = registrar_cliente(
            nome=requisicao.nome,
            descricao=requisicao.descricao
        )
    except ValueError as erro:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(erro)
        )

    return RespostaRegistroCliente(
        cliente_id=resultado["cliente_id"],
        nome=resultado["nome"],
        api_key=resultado["api_key"],
        criado_em=resultado["criado_em"]
    )


@roteador_admin.get(
    "/clientes",
    response_model=RespostaListaClientes,
    status_code=status.HTTP_200_OK,
    summary="Listar todos os clientes",
    description="Retorna a lista de todos os clientes cadastrados na API sem expor API Keys."
)
async def listar_todos_clientes(
    x_admin_key: str = Header(..., description="Chave de administracao da API")
) -> RespostaListaClientes:
    """Lista todos os clientes cadastrados sem expor informacoes sensiveis.

    Args:
        x_admin_key (str): Chave administrativa para autorizar a operacao.

    Returns:
        RespostaListaClientes: Lista de clientes com dados publicos e total.
    """
    _validar_admin_key(x_admin_key)

    clientes = listar_clientes()

    return RespostaListaClientes(
        total=len(clientes),
        clientes=clientes
    )


@roteador_admin.delete(
    "/clientes/{cliente_id}",
    status_code=status.HTTP_200_OK,
    summary="Revogar (desativar) um cliente",
    description="Desativa um cliente, impedindo-o de gerar novos tokens. Tokens ativos permanecem validos ate expirarem."
)
async def desativar_cliente(
    cliente_id: str,
    x_admin_key: str = Header(..., description="Chave de administracao da API")
) -> dict:
    """Desativa um cliente pelo seu identificador unico.

    Args:
        cliente_id (str): Identificador unico do cliente a desativar.
        x_admin_key (str): Chave administrativa para autorizar a operacao.

    Returns:
        dict: Mensagem de confirmacao da desativacao.

    Raises:
        HTTPException (404): Se o cliente nao for encontrado.
    """
    _validar_admin_key(x_admin_key)

    sucesso = revogar_cliente(cliente_id)

    if not sucesso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente '{cliente_id}' nao encontrado."
        )

    return {
        "mensagem": f"Cliente '{cliente_id}' desativado com sucesso.",
        "desativado": True
    }


@roteador_admin.get(
    "/metricas",
    status_code=status.HTTP_200_OK,
    summary="Obter metricas de consumo",
    description="Retorna o consolidado de todas as chamadas realizadas a API por cliente e por modelo."
)
async def relatorio_metricas(
    x_admin_key: str = Header(..., description="Chave de administracao da API")
) -> dict:
    """Retorna as metricas de uso do sistema.

    Args:
        x_admin_key (str): Chave administrativa para autorizar a operacao.

    Returns:
        dict: Metricas de todos os clientes.
    """
    _validar_admin_key(x_admin_key)

    metricas = obter_metricas()
    
    return {
        "total_clientes_com_consumo": len(metricas),
        "metricas": metricas
    }
