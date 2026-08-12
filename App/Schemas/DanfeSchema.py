"""Schemas Pydantic para validação e estruturação dos dados extraídos de DANFE.

Este módulo define a estrutura oficial dos dados de uma Nota Fiscal Eletrônica (DANFE),
garantindo tipagem rigorosa para consumo por APIs externas e geração de relatórios.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DadosEmitente(BaseModel):
    """Estrutura referente às informações do emitente da nota fiscal."""

    razao_social: Optional[str] = Field(None, description="Razão Social ou Nome do Emitente")
    nome_fantasia: Optional[str] = Field(None, description="Nome Fantasia do Emitente")
    cnpj: Optional[str] = Field(None, description="CNPJ do Emitente")
    inscricao_estadual: Optional[str] = Field(None, description="Inscrição Estadual do Emitente")
    endereco: Optional[str] = Field(None, description="Logradouro e número")
    bairro: Optional[str] = Field(None, description="Bairro do emitente")
    municipio: Optional[str] = Field(None, description="Cidade do emitente")
    uf: Optional[str] = Field(None, description="Sigla do Estado (UF)")
    cep: Optional[str] = Field(None, description="Código de Endereçamento Postal (CEP)")
    telefone: Optional[str] = Field(None, description="Telefone de contato do emitente")


class DadosDestinatario(BaseModel):
    """Estrutura referente às informações do destinatário/remetente da nota fiscal."""

    razao_social: Optional[str] = Field(None, description="Razão Social ou Nome do Destinatário")
    cnpj_cpf: Optional[str] = Field(None, description="CNPJ ou CPF do Destinatário")
    inscricao_estadual: Optional[str] = Field(None, description="Inscrição Estadual do Destinatário")
    endereco: Optional[str] = Field(None, description="Logradouro e número")
    bairro: Optional[str] = Field(None, description="Bairro do destinatário")
    municipio: Optional[str] = Field(None, description="Cidade do destinatário")
    uf: Optional[str] = Field(None, description="Sigla do Estado (UF)")
    cep: Optional[str] = Field(None, description="CEP do destinatário")


class ValoresTotaisDANFE(BaseModel):
    """Valores consolidados dos impostos e totais da DANFE."""

    base_calculo_icms: Optional[float] = Field(0.0, description="Base de cálculo do ICMS")
    valor_icms: Optional[float] = Field(0.0, description="Valor total do ICMS")
    base_calculo_icms_st: Optional[float] = Field(0.0, description="Base de cálculo do ICMS ST")
    valor_icms_st: Optional[float] = Field(0.0, description="Valor total do ICMS ST")
    valor_total_produtos: Optional[float] = Field(0.0, description="Valor total dos produtos ou serviços")
    valor_frete: Optional[float] = Field(0.0, description="Valor total do frete")
    valor_seguro: Optional[float] = Field(0.0, description="Valor total do seguro")
    desconto: Optional[float] = Field(0.0, description="Valor total de descontos")
    outras_despesas: Optional[float] = Field(0.0, description="Outras despesas acessórias")
    valor_ipi: Optional[float] = Field(0.0, description="Valor total do IPI")
    valor_total_nota: Optional[float] = Field(0.0, description="Valor total da nota fiscal")


class DadosTransportador(BaseModel):
    """Dados da empresa de transporte e veículo."""

    razao_social: Optional[str] = Field(None, description="Razão Social do Transportador")
    cnpj_cpf: Optional[str] = Field(None, description="CNPJ ou CPF do Transportador")
    inscricao_estadual: Optional[str] = Field(None, description="Inscrição Estadual do Transportador")
    placa_veiculo: Optional[str] = Field(None, description="Placa do Veículo")
    uf_veiculo: Optional[str] = Field(None, description="UF da Placa do Veículo")


class ItemDANFE(BaseModel):
    """Detalhamento individual de cada produto ou serviço presente na DANFE."""

    codigo_produto: Optional[str] = Field(None, description="Código interno do produto")
    descricao: Optional[str] = Field(None, description="Descrição detalhada do produto ou serviço")
    ncm_sh: Optional[str] = Field(None, description="Código NCM/SH")
    cst_csosn: Optional[str] = Field(None, description="Código CST ou CSOSN")
    cfop: Optional[str] = Field(None, description="Código CFOP")
    unidade: Optional[str] = Field(None, description="Unidade de medida (ex: UN, KG, CX)")
    quantidade: Optional[float] = Field(0.0, description="Quantidade comercializada")
    valor_unitario: Optional[float] = Field(0.0, description="Valor unitário do item")
    valor_total: Optional[float] = Field(0.0, description="Valor total do item")
    aliquota_icms: Optional[float] = Field(0.0, description="Alíquota de ICMS (%)")
    aliquota_ipi: Optional[float] = Field(0.0, description="Alíquota de IPI (%)")


class DadosDANFE(BaseModel):
    """Modelo completo contendo todos os dados estruturados extraídos da DANFE."""

    chave_acesso: Optional[str] = Field(None, description="Chave de acesso de 44 dígitos numéricos")
    numero_nota: Optional[str] = Field(None, description="Número da Nota Fiscal")
    serie: Optional[str] = Field(None, description="Série da Nota Fiscal")
    natureza_operacao: Optional[str] = Field(None, description="Descrição da Natureza da Operação")
    tipo_operacao: Optional[str] = Field(None, description="0 - Entrada, 1 - Saída")
    data_emissao: Optional[str] = Field(None, description="Data de emissão no formato DD/MM/YYYY")
    data_saida_entrada: Optional[str] = Field(None, description="Data de saída ou entrada no formato DD/MM/YYYY")

    emitente: Optional[DadosEmitente] = Field(default_factory=DadosEmitente)
    destinatario: Optional[DadosDestinatario] = Field(default_factory=DadosDestinatario)
    valores_totais: Optional[ValoresTotaisDANFE] = Field(default_factory=ValoresTotaisDANFE)
    transportador: Optional[DadosTransportador] = Field(default_factory=DadosTransportador)
    itens: List[ItemDANFE] = Field(default_factory=list, description="Lista dos itens contidos na nota fiscal")


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
    dados: Optional[DadosDANFE] = Field(None, description="Dados estruturados da DANFE extraída")
    metadados: Optional[MetadadosProcessamento] = Field(None, description="Metadados técnicos da requisição")
