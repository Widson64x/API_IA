"""Schemas Pydantic para validação e estruturação dos dados extraídos de DANFE.

Este módulo define a nova estrutura oficial dos dados de extração de Nota Fiscal,
refletindo os detalhes de origem e destino, além das devoluções e importações.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Entidade(BaseModel):
    """Representa uma entidade (Remetente ou Destinatário) envolvida na transação."""
    nome: Optional[str] = Field(None, description="Nome ou Razão Social")
    cnpj: Optional[str] = Field(None, description="CNPJ (apenas números)")
    cep: Optional[str] = Field(None, description="CEP (apenas números)")
    endereco: Optional[str] = Field(None, description="Endereço principal")
    cidade: Optional[str] = Field(None, description="Cidade")
    uf: Optional[str] = Field(None, description="UF (Estado)")
    bairro: Optional[str] = Field(None, description="Bairro")
    numero: Optional[str] = Field(None, description="Número do endereço")


class DadosNota(BaseModel):
    """Dados específicos de uma nota (seja ela original ou de devolução)."""
    numero: Optional[str] = Field(None, description="Número da nota fiscal")
    serie: Optional[str] = Field(None, description="Série da nota fiscal")
    data: Optional[str] = Field(None, description="Data de emissão (YYYY-MM-DD)")
    peso: Optional[float] = Field(0.0, description="Peso bruto ou líquido")
    volume: Optional[float] = Field(0.0, description="Volume ou quantidade transportada")
    valor: Optional[float] = Field(0.0, description="Valor total da nota")


class NotaFiscalItem(BaseModel):
    """Detalhamento individual das informações extraídas do documento."""
    
    Remetente: Optional[Entidade] = Field(None, description="Dados de quem emitiu a nota atual")
    Destinatario: Optional[Entidade] = Field(None, description="Dados de quem receberá a carga/nota atual")
    
    NFO: Optional[DadosNota] = Field(None, description="Dados da Nota Fiscal Original (Venda/Remessa)")
    NFD: Optional[DadosNota] = Field(None, description="Dados da Nota Fiscal de Devolução (se houver)")
    
    pedido: Optional[str] = Field(None, description="Número do pedido referenciado")


class DadosDANFE(BaseModel):
    """Modelo completo contendo os dados estruturados da NF conforme o novo layout padrão."""

    arquivo: Optional[str] = Field(None, description="Identificador do arquivo")
    extensao: Optional[str] = Field(None, description="Extensão do arquivo")
    tamanho: Optional[str] = Field(None, description="Tamanho do arquivo")
    data_criacao: Optional[str] = Field(None, description="Data de criação")
    quantidade_nota: Optional[int] = Field(0, description="Quantidade total de notas")
    notaFiscalList: List[NotaFiscalItem] = Field(default_factory=list, description="Lista de notas fiscais extraídas")


class MetadadosProcessamento(BaseModel):
    """Metadados técnicos sobre a execução da extração por IA."""

    modelo_utilizado: str = Field(..., description="Nome ou chave do modelo de IA utilizado")
    provedor: str = Field(..., description="Nome do provedor")
    tempo_execucao_segundos: float = Field(..., description="Tempo total gasto no processamento")
    nome_arquivo_original: str = Field(..., description="Nome do arquivo enviado pelo cliente")


class RequisicaoExtracaoB64(BaseModel):
    """Payload de entrada para extração de DANFE via arquivo codificado em Base64."""

    tipo_arquivo: str = Field(..., description="Extensão ou tipo do arquivo (ex: 'pdf', 'png', 'jpg', 'jpeg', 'webp')")
    arquivo_b64: str = Field(..., description="Conteúdo do arquivo codificado em base64 (suporta data URL ou b64 puro)")
    modelo_ia: Optional[str] = Field("gemini", description="Modelo de IA a utilizar (gemini, openai, claude, deepseek, etc.)")
    nome_arquivo: Optional[str] = Field(None, description="Nome opcional do arquivo (ex: 'nota_fiscal.pdf')")


class RespostaExtracaoDANFE(BaseModel):
    """Payload de resposta padrão retornado pela API."""

    sucesso: bool = Field(..., description="Indica se a extração foi concluída com sucesso")
    mensagem: str = Field(..., description="Mensagem descritiva")
    dados: Optional[DadosDANFE] = Field(None, description="Dados estruturados extraídos")
    metadados: Optional[MetadadosProcessamento] = Field(None, description="Metadados técnicos")
