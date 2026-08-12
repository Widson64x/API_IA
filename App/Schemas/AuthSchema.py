"""Schemas Pydantic para autenticacao, tokens JWT e gestao de clientes.

Define os modelos de entrada e saida dos endpoints de autenticacao,
garantindo validacao rigorosa e documentacao automatica no Swagger.
"""

from typing import Optional
from pydantic import BaseModel, Field


class RequisicaoToken(BaseModel):
    """Payload de entrada para solicitar um par de tokens JWT via API Key.

    Attributes:
        api_key (str): API Key do cliente em texto plano.
    """

    api_key: str = Field(
        ...,
        description="API Key do cliente para autenticacao.",
        min_length=10,
        examples=["idocs_a1b2c3d4e5f6..."]
    )


class RespostaToken(BaseModel):
    """Payload de resposta contendo o par de tokens JWT gerados.

    Attributes:
        access_token (str): Token de acesso de curta duracao.
        refresh_token (str): Token de renovacao de longa duracao.
        token_type (str): Tipo de autenticacao (sempre 'bearer').
        expira_em_minutos (int): Tempo de vida do access token em minutos.
    """

    access_token: str = Field(..., description="JWT access token para acesso aos endpoints.")
    refresh_token: str = Field(..., description="JWT refresh token para renovacao de sessao.")
    token_type: str = Field(default="bearer", description="Tipo de autenticacao HTTP.")
    expira_em_minutos: int = Field(..., description="Tempo de vida do access token em minutos.")


class RequisicaoRefreshToken(BaseModel):
    """Payload de entrada para renovar o access token usando o refresh token.

    Attributes:
        refresh_token (str): Refresh token JWT valido.
    """

    refresh_token: str = Field(
        ...,
        description="Refresh token JWT para renovacao do access token.",
        min_length=10
    )


class RequisicaoRevogacao(BaseModel):
    """Payload de entrada para revogar (invalidar) um token ativo.

    Attributes:
        token (str): Token JWT a ser revogado.
    """

    token: str = Field(
        ...,
        description="Token JWT (access ou refresh) a ser revogado.",
        min_length=10
    )


class DadosCliente(BaseModel):
    """Representacao publica dos dados de um cliente autenticado.

    Attributes:
        cliente_id (str): Identificador unico do cliente.
        nome (str): Nome do cliente.
        descricao (str): Descricao do proposito do cliente.
    """

    cliente_id: str = Field(..., description="Identificador unico do cliente.")
    nome: str = Field(..., description="Nome do cliente.")
    descricao: str = Field(default="", description="Descricao do proposito do cliente.")


class RequisicaoRegistroCliente(BaseModel):
    """Payload de entrada para registro de um novo cliente (uso administrativo).

    Attributes:
        nome (str): Nome identificador do cliente.
        descricao (str): Descricao opcional do proposito do cliente.
    """

    nome: str = Field(
        ...,
        description="Nome identificador do cliente (ex: 'Sistema ERP Matriz').",
        min_length=3,
        max_length=100
    )
    descricao: str = Field(
        default="",
        description="Descricao opcional do proposito do cliente.",
        max_length=500
    )


class RespostaRegistroCliente(BaseModel):
    """Payload de resposta apos registro de um novo cliente.

    A API Key aparece em texto plano APENAS nesta resposta.
    O cliente deve armazena-la de forma segura, pois nao sera exibida novamente.

    Attributes:
        cliente_id (str): Identificador unico gerado.
        nome (str): Nome do cliente registrado.
        api_key (str): API Key gerada (exibida apenas uma vez).
        criado_em (str): Timestamp ISO 8601 da criacao.
        aviso (str): Mensagem alertando para armazenar a key com seguranca.
    """

    cliente_id: str = Field(..., description="Identificador unico do cliente.")
    nome: str = Field(..., description="Nome do cliente registrado.")
    api_key: str = Field(..., description="API Key gerada. Armazene com seguranca, nao sera exibida novamente.")
    criado_em: str = Field(..., description="Timestamp de criacao em formato ISO 8601.")
    aviso: str = Field(
        default="Armazene esta API Key em local seguro. Ela nao sera exibida novamente.",
        description="Aviso de seguranca sobre a API Key."
    )


class RespostaListaClientes(BaseModel):
    """Payload de resposta para listagem de clientes cadastrados.

    Attributes:
        total (int): Quantidade total de clientes.
        clientes (list[dict]): Lista de dados publicos dos clientes.
    """

    total: int = Field(..., description="Quantidade total de clientes cadastrados.")
    clientes: list[dict] = Field(..., description="Lista de clientes com dados publicos.")
