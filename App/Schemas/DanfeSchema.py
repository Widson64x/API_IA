"""Schemas Pydantic para validação e estruturação dos dados extraídos de DANFE.

Este módulo define a nova estrutura oficial dos dados de extração de Nota Fiscal,
refletindo os detalhes de origem e destino, além das devoluções e importações.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class NotaFiscalItem(BaseModel):
    """Detalhamento individual das informações de origem, destino e valores da nota."""

    origem_nome: Optional[str] = Field(None, description="Nome ou Razão Social da origem")
    origem_cnpj: Optional[str] = Field(None, description="CNPJ da origem")
    origem_cep: Optional[str] = Field(None, description="CEP da origem")
    origem_endereco: Optional[str] = Field(None, description="Endereço da origem")
    origem_cidade: Optional[str] = Field(None, description="Cidade da origem")
    origem_uf: Optional[str] = Field(None, description="UF da origem")
    origem_bairro: Optional[str] = Field(None, description="Bairro da origem")
    origem_numero: Optional[str] = Field(None, description="Número do endereço da origem")
    
    destino_nome: Optional[str] = Field(None, description="Nome ou Razão Social do destino")
    destino_cnpj: Optional[str] = Field(None, description="CNPJ do destino")
    destino_cep: Optional[str] = Field(None, description="CEP do destino")
    destino_endereco: Optional[str] = Field(None, description="Endereço do destino")
    destino_cidade: Optional[str] = Field(None, description="Cidade do destino")
    destino_uf: Optional[str] = Field(None, description="UF do destino")
    destino_bairro: Optional[str] = Field(None, description="Bairro do destino")
    destino_numero: Optional[str] = Field(None, description="Número do endereço do destino")
    
    devolucao_nota: Optional[str] = Field(None, description="Número da nota de devolução")
    devolucao_serie: Optional[str] = Field(None, description="Série da nota de devolução")
    origem_nota: Optional[str] = Field(None, description="Número da nota de origem")
    origem_serie: Optional[str] = Field(None, description="Série da nota de origem")
    origem_data: Optional[str] = Field(None, description="Data de origem no formato YYYY-MM-DD")
    pedido: Optional[str] = Field(None, description="Número do pedido")
    
    devolucao_peso: Optional[float] = Field(0.0, description="Peso da devolução")
    devolucao_volume: Optional[float] = Field(0.0, description="Volume da devolução")
    devolucao_valor: Optional[float] = Field(0.0, description="Valor da devolução")


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
    provedor: str = Field(..., description="Nome do provedor (Gemini, OpenAI, Claude, DeepSeek, OpenRouter)")
    tempo_execucao_segundos: float = Field(..., description="Tempo total gasto no processamento")
    nome_arquivo_original: str = Field(..., description="Nome do arquivo enviado pelo cliente")


class RespostaExtracaoDANFE(BaseModel):
    """Payload de resposta padrão retornado pela API."""

    sucesso: bool = Field(..., description="Indica se a extração foi concluída com sucesso")
    mensagem: str = Field(..., description="Mensagem descritiva do resultado da operação")
    dados: Optional[DadosDANFE] = Field(None, description="Dados estruturados da NF extraída")
    metadados: Optional[MetadadosProcessamento] = Field(None, description="Metadados técnicos da requisição")
