"""Schemas de validação dos dados extraídos de documentos fiscais."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ModeloDANFE(BaseModel):
    """Configuração comum: ignora campos inesperados e remove espaços externos."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Entidade(ModeloDANFE):
    """Empresa emitente ou destinatária da nota fiscal."""

    nome: Optional[str] = Field(None, description="Nome ou razão social")
    cnpj: Optional[str] = Field(None, description="CNPJ, somente com dígitos")
    cep: Optional[str] = Field(None, description="CEP, somente com dígitos")
    endereco: Optional[str] = Field(None, description="Logradouro")
    cidade: Optional[str] = Field(None, description="Município")
    uf: Optional[str] = Field(None, description="UF")
    bairro: Optional[str] = Field(None, description="Bairro ou distrito")
    numero: Optional[str] = Field(None, description="Número do endereço")


class DadosNota(ModeloDANFE):
    """Dados de uma nota fiscal original ou de devolução."""

    numero: Optional[str] = Field(None, description="Número da nota fiscal")
    serie: Optional[str] = Field(None, description="Série da nota fiscal")
    data: Optional[str] = Field(None, description="Data de emissão no formato YYYY-MM-DD")
    chave_acesso: Optional[str] = Field(
        None,
        description="Chave de acesso da NF-e, com exatamente 44 dígitos",
    )
    peso: Optional[float] = Field(None, description="Peso bruto em kg")
    volume: Optional[float] = Field(None, description="Quantidade de volumes")
    valor: Optional[float] = Field(None, description="Valor total da nota")


class NotaFiscalItem(ModeloDANFE):
    """Uma DANFE identificada no documento enviado."""

    Remetente: Optional[Entidade] = Field(
        None,
        description="Emitente identificado no cabeçalho da DANFE",
    )
    Destinatario: Optional[Entidade] = Field(
        None,
        description="Empresa do quadro DESTINATÁRIO / REMETENTE",
    )
    NFO: Optional[DadosNota] = Field(
        None,
        description="Nota fiscal original referenciada pela devolução",
    )
    NFD: Optional[DadosNota] = Field(
        None,
        description="Nota fiscal de devolução exibida no cabeçalho da DANFE",
    )
    pedido: Optional[str] = Field(
        None,
        description="Número explicitamente identificado como pedido",
    )


class DadosDANFE(ModeloDANFE):
    """Resultado estruturado da extração de um arquivo."""

    arquivo: Optional[str] = Field(None, description="Nome do arquivo sem extensão")
    extensao: Optional[str] = Field(None, description="Extensão do arquivo sem ponto")
    tamanho: Optional[str] = Field(None, description="Tamanho exato do arquivo em bytes")
    data_criacao: Optional[str] = Field(
        None,
        description="Data de criação presente nos metadados do documento",
    )
    quantidade_nota: int = Field(0, description="Quantidade de DANFEs identificadas")
    notaFiscalList: List[NotaFiscalItem] = Field(
        default_factory=list,
        description="Uma entrada por DANFE; anexos e DACTEs não geram entradas",
    )


class MetadadosProcessamento(ModeloDANFE):
    """Metadados técnicos da execução."""

    modelo_utilizado: str = Field(..., description="Modelo solicitado")
    provedor: str = Field(..., description="Provedor utilizado")
    tempo_execucao_segundos: float = Field(..., description="Tempo de processamento")
    nome_arquivo_original: str = Field(..., description="Nome original do upload")


class RequisicaoExtracaoB64(ModeloDANFE):
    """Entrada para extração de um documento codificado em Base64."""

    tipo_arquivo: str = Field(
        ...,
        description="Extensão do arquivo: pdf, png, jpg, jpeg ou webp",
    )
    arquivo_b64: str = Field(
        ...,
        min_length=1,
        description="Base64 puro ou data URL contendo o documento",
    )
    modelo_ia: str = Field(
        "gemini",
        description="Provedor de IA configurado na aplicação",
    )
    nome_arquivo: Optional[str] = Field(
        None,
        description="Nome opcional do arquivo com extensão",
    )


class RespostaExtracaoDANFE(ModeloDANFE):
    """Resposta pública do endpoint de extração."""

    sucesso: bool
    mensagem: str
    dados: Optional[DadosDANFE] = None
    metadados: Optional[MetadadosProcessamento] = None
