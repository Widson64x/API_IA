"""Implementação do extrator de DANFE utilizando modelos da Anthropic Claude (ex: claude-3-5-sonnet).

Utiliza o SDK assíncrono da Anthropic enviando dados nativos de PDF ou imagens em base64.
"""

import base64
from anthropic import AsyncAnthropic

from App.Core.Config import configuracao
from App.Schemas.DanfeSchema import DadosDANFE
from App.Services.BaseExtractorService import DANFEExtratorBase


class ExtratorClaude(DANFEExtratorBase):
    """Extrator de dados de DANFE utilizando a API da Anthropic.

    Attributes:
        nome_modelo (str): Identificador do modelo Claude (ex: claude-3-5-sonnet-20241022).
    """

    def __init__(self, nome_modelo: str = "claude-3-5-sonnet-20241022"):
        """Inicializa o extrator Claude.

        Args:
            nome_modelo (str): Identificador do modelo Anthropic.
        """
        self.nome_modelo = nome_modelo
        self.api_key = configuracao.ANTHROPIC_API_KEY

    async def extrair_dados(self, conteudo_arquivo: bytes, nome_arquivo: str) -> DadosDANFE:
        """Extrai os dados da DANFE via API Anthropic Claude.

        Args:
            conteudo_arquivo (bytes): Conteúdo binário do arquivo.
            nome_arquivo (str): Nome do arquivo original.

        Returns:
            DadosDANFE: Instância validada do Pydantic com os dados lidos.

        Raises:
            ValueError: Se a chave ANTHROPIC_API_KEY não estiver configurada.
        """
        if not self.api_key:
            raise ValueError("A chave ANTHROPIC_API_KEY não foi configurada no arquivo .env")

        prompt = self._obter_prompt_instrucao()
        extensao = nome_arquivo.lower().split(".")[-1]

        b64_data = base64.b64encode(conteudo_arquivo).decode("utf-8")

        # Configura o bloco de conteúdo visual ou de documento para a API da Anthropic
        if extensao == "pdf":
            bloco_midia = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64_data
                }
            }
        else:
            media_type = f"image/{'jpeg' if extensao == 'jpg' else extensao}"
            bloco_midia = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64_data
                }
            }

        cliente = AsyncAnthropic(api_key=self.api_key)
        
        resposta = await cliente.messages.create(
            model=self.nome_modelo,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [bloco_midia, {"type": "text", "text": prompt}]
                }
            ]
        )

        texto_resposta = resposta.content[0].text
        dados_dict = self._limpar_e_converter_json(texto_resposta)
        return DadosDANFE(**dados_dict)
