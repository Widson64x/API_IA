"""Implementação do extrator de DANFE utilizando modelos OpenAI (GPT-4o, GPT-4o-mini).

Converte documentos para formato visual (base64) e utiliza capacidades de visão e JSON mode.
"""

import base64
from openai import AsyncOpenAI

from App.Core.Config import configuracao
from App.Schemas.DanfeSchema import DadosDANFE
from App.Services.BaseExtractorService import DANFEExtratorBase


class ExtratorOpenAI(DANFEExtratorBase):
    """Extrator de dados de DANFE utilizando a API da OpenAI.

    Attributes:
        nome_modelo (str): Identificador do modelo OpenAI (ex: gpt-4o-mini, gpt-4o).
    """

    def __init__(self, nome_modelo: str = "gpt-4o-mini"):
        """Inicializa o extrator OpenAI.

        Args:
            nome_modelo (str): Identificador do modelo. Padrão 'gpt-4o-mini'.
        """
        self.nome_modelo = nome_modelo
        self.api_key = configuracao.OPENAI_API_KEY

    async def extrair_dados(self, conteudo_arquivo: bytes, nome_arquivo: str) -> DadosDANFE:
        """Processa a DANFE via API da OpenAI.

        Se o arquivo for PDF, converte as páginas em imagens em memória antes de enviar à API.

        Args:
            conteudo_arquivo (bytes): Conteúdo binário do arquivo.
            nome_arquivo (str): Nome do arquivo com extensão.

        Returns:
            DadosDANFE: Dados da DANFE estruturados no modelo Pydantic.

        Raises:
            ValueError: Se a chave OPENAI_API_KEY não estiver definida.
        """
        if not self.api_key:
            raise ValueError("A chave OPENAI_API_KEY não foi configurada no arquivo .env")

        prompt = self._obter_prompt_instrucao()
        extensao = nome_arquivo.lower().split(".")[-1]

        # Se for PDF, renderiza as páginas em imagens PNG
        if extensao == "pdf":
            lista_imagens = self._converter_pdf_para_imagens(conteudo_arquivo)
        else:
            lista_imagens = [conteudo_arquivo]

        conteudo_requisicao = [{"type": "text", "text": prompt}]

        for imagem_bytes in lista_imagens:
            base64_imagem = base64.b64encode(imagem_bytes).decode("utf-8")
            conteudo_requisicao.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_imagem}"
                }
            })

        cliente = AsyncOpenAI(api_key=self.api_key)
        
        resposta = await cliente.chat.completions.create(
            model=self.nome_modelo,
            messages=[
                {"role": "user", "content": conteudo_requisicao}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        texto_resposta = resposta.choices[0].message.content
        dados_dict = self._limpar_e_converter_json(texto_resposta)
        dados_dict = self._preencher_metadados_arquivo(dados_dict, nome_arquivo, len(conteudo_arquivo))
        return DadosDANFE(**dados_dict)
