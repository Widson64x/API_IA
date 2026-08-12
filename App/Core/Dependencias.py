"""FastAPI Dependencies para injecao de autenticacao e rate limiting nos endpoints.

Fornece funcoes de dependencia reutilizaveis que extraem e validam
o token JWT do header Authorization, retornando os dados do cliente
autenticado e aplicando controle de taxa de requisicoes.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from App.Core.RateLimiter import verificar_limite
from App.Core.Seguranca import decodificar_token
from App.Schemas.AuthSchema import DadosCliente


# Esquema de seguranca HTTPBearer - extrai automaticamente o token do header Authorization
_esquema_bearer = HTTPBearer(
    scheme_name="JWT Bearer Token",
    description="Insira o access token JWT obtido via /api/v1/auth/token"
)


async def obter_cliente_autenticado(
    credenciais: HTTPAuthorizationCredentials = Depends(_esquema_bearer)
) -> DadosCliente:
    """Dependency que extrai, valida o JWT e retorna os dados do cliente autenticado.

    Fluxo:
    1. Extrai o token do header 'Authorization: Bearer <token>'
    2. Decodifica e valida o JWT (assinatura, expiracao, revogacao)
    3. Verifica se o tipo do token e 'access' (rejeita refresh tokens)
    4. Retorna DadosCliente para uso no endpoint

    Args:
        credenciais (HTTPAuthorizationCredentials): Credenciais extraidas pelo HTTPBearer.

    Returns:
        DadosCliente: Dados do cliente autenticado (cliente_id, nome, descricao).

    Raises:
        HTTPException (401): Token ausente, invalido, expirado ou revogado.
        HTTPException (401): Token nao e do tipo 'access'.
    """
    token = credenciais.credentials

    try:
        payload = decodificar_token(token)
    except ValueError as erro:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(erro),
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Rejeita refresh tokens usados como access tokens
    if payload.get("tipo") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token informado nao e um access token valido.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extrai os dados do cliente dos claims do JWT
    cliente_id = payload.get("sub")
    nome = payload.get("nome", "")
    descricao = payload.get("descricao", "")

    if not cliente_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido: identificador do cliente ausente.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return DadosCliente(
        cliente_id=cliente_id,
        nome=nome,
        descricao=descricao
    )


async def aplicar_rate_limit(
    request: Request,
    cliente: DadosCliente = Depends(obter_cliente_autenticado)
) -> DadosCliente:
    """Dependency composta que autentica o cliente E aplica rate limiting.

    Combina autenticacao JWT com controle de taxa em uma unica dependency.
    Adiciona headers de rate limit na resposta via request.state.

    Args:
        request (Request): Objeto de requisicao FastAPI para armazenar headers.
        cliente (DadosCliente): Cliente autenticado (injetado automaticamente).

    Returns:
        DadosCliente: Dados do cliente autenticado.

    Raises:
        HTTPException (429): Se o cliente excedeu o limite de requisicoes.
    """
    try:
        info_limite = verificar_limite(cliente.cliente_id)
        # Armazena info de rate limit no request.state para o middleware adicionar os headers
        request.state.rate_limit_info = info_limite
    except ValueError as erro:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(erro),
            headers={"Retry-After": "60"}
        )

    return cliente
