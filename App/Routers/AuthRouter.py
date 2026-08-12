"""Roteador FastAPI para endpoints de autenticacao JWT.

Disponibiliza endpoints para obtencao de tokens via API Key,
renovacao de sessao via refresh token, revogacao de tokens
e consulta do perfil do cliente autenticado.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from App.Core.Dependencias import obter_cliente_autenticado
from App.Core.GerenciadorApiKeys import autenticar_por_api_key
from App.Core.Seguranca import (
    criar_access_token,
    criar_refresh_token,
    decodificar_token,
    revogar_token,
)
from App.Core.Config import configuracao
from App.Schemas.AuthSchema import (
    DadosCliente,
    RequisicaoRefreshToken,
    RequisicaoRevogacao,
    RequisicaoToken,
    RespostaToken,
)

roteador_auth = APIRouter(prefix="/api/v1/auth", tags=["Autenticacao"])


@roteador_auth.post(
    "/token",
    response_model=RespostaToken,
    status_code=status.HTTP_200_OK,
    summary="Obter tokens JWT via API Key",
    description=(
        "Autentica o cliente usando sua API Key e retorna um par de tokens JWT "
        "(access + refresh). O access token deve ser usado no header "
        "'Authorization: Bearer <token>' para acessar endpoints protegidos."
    )
)
async def obter_token(requisicao: RequisicaoToken) -> RespostaToken:
    """Gera um par de tokens JWT a partir de uma API Key valida.

    Args:
        requisicao (RequisicaoToken): Payload contendo a API Key do cliente.

    Returns:
        RespostaToken: Par de tokens JWT com metadados de expiracao.

    Raises:
        HTTPException (401): Se a API Key for invalida ou o cliente estiver desativado.
    """
    cliente = autenticar_por_api_key(requisicao.api_key)

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key invalida ou cliente desativado."
        )

    # Claims que serao embedados no JWT
    claims_token = {
        "sub": cliente["cliente_id"],
        "nome": cliente["nome"],
        "descricao": cliente["descricao"]
    }

    access_token = criar_access_token(claims_token)
    refresh_token = criar_refresh_token({"sub": cliente["cliente_id"]})

    return RespostaToken(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expira_em_minutos=configuracao.ACCESS_TOKEN_DURACAO_MINUTOS
    )


@roteador_auth.post(
    "/refresh",
    response_model=RespostaToken,
    status_code=status.HTTP_200_OK,
    summary="Renovar access token via refresh token",
    description=(
        "Gera um novo par de tokens JWT a partir de um refresh token valido. "
        "O refresh token anterior e automaticamente revogado para prevenir reuso."
    )
)
async def renovar_token(requisicao: RequisicaoRefreshToken) -> RespostaToken:
    """Renova o access token usando um refresh token valido.

    O refresh token antigo e revogado apos o uso (rotacao de tokens).

    Args:
        requisicao (RequisicaoRefreshToken): Payload contendo o refresh token.

    Returns:
        RespostaToken: Novo par de tokens JWT.

    Raises:
        HTTPException (401): Se o refresh token for invalido, expirado ou revogado.
    """
    try:
        payload = decodificar_token(requisicao.refresh_token)
    except ValueError as erro:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(erro)
        )

    if payload.get("tipo") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token informado nao e um refresh token valido."
        )

    # Revoga o refresh token antigo (rotacao de tokens - previne replay attacks)
    jti_antigo = payload.get("jti")
    if jti_antigo:
        revogar_token(jti_antigo)

    cliente_id = payload.get("sub")
    claims_token = {"sub": cliente_id, "nome": payload.get("nome", ""), "descricao": payload.get("descricao", "")}

    novo_access = criar_access_token(claims_token)
    novo_refresh = criar_refresh_token({"sub": cliente_id})

    return RespostaToken(
        access_token=novo_access,
        refresh_token=novo_refresh,
        token_type="bearer",
        expira_em_minutos=configuracao.ACCESS_TOKEN_DURACAO_MINUTOS
    )


@roteador_auth.post(
    "/revogar",
    status_code=status.HTTP_200_OK,
    summary="Revogar um token JWT ativo",
    description="Invalida um token JWT (access ou refresh), impedindo seu uso posterior."
)
async def revogar_token_endpoint(requisicao: RequisicaoRevogacao) -> dict:
    """Revoga (invalida) um token JWT ativo, adicionando-o a blacklist.

    Args:
        requisicao (RequisicaoRevogacao): Payload contendo o token a ser revogado.

    Returns:
        dict: Mensagem de confirmacao da revogacao.

    Raises:
        HTTPException (400): Se o token for invalido ou ja estiver expirado.
    """
    try:
        payload = decodificar_token(requisicao.token)
    except ValueError as erro:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nao foi possivel revogar o token: {str(erro)}"
        )

    jti = payload.get("jti")
    if jti:
        revogar_token(jti)

    return {"mensagem": "Token revogado com sucesso.", "revogado": True}


@roteador_auth.get(
    "/perfil",
    response_model=DadosCliente,
    status_code=status.HTTP_200_OK,
    summary="Consultar perfil do cliente autenticado",
    description="Retorna os dados do cliente associado ao access token JWT informado."
)
async def obter_perfil(
    cliente: DadosCliente = Depends(obter_cliente_autenticado)
) -> DadosCliente:
    """Retorna os dados do cliente autenticado pelo JWT.

    Args:
        cliente (DadosCliente): Dados do cliente injetados pela dependency de autenticacao.

    Returns:
        DadosCliente: Dados publicos do cliente (id, nome, descricao).
    """
    return cliente
