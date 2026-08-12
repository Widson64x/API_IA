"""Implementação do extrator de NF utilizando Groq.

Integração com a API ultrarrápida da Groq para extração de dados utilizando
modelo Qwen 3.6 27B Vision.
"""

import base64
from openai import AsyncOpenAI

from App.Core.Config import configuracao
from App.Schemas.DanfeSchema import DadosDANFE
from App.Services.BaseExtractorService import DANFEExtratorBase


class ExtratorGroq(DANFEExtratorBase):
    """Extrator de dados de NF utilizando a API da Groq.

    Attributes:
        nome_modelo (str): Identificador do modelo Vision (ex: qwen/qwen3.6-27b).
    """

    def __init__(self, nome_modelo: str = "qwen/qwen3.6-27b"):
        """Inicializa o extrator Groq.

        Args:
            nome_modelo (str): O modelo hospedado na Groq (padrão: Qwen 3.6 27B Vision).
        """
        self.nome_modelo = nome_modelo
        self.api_key = configuracao.GROQ_API_KEY

    async def extrair_dados(self, conteudo_arquivo: bytes, nome_arquivo: str) -> DadosDANFE:
        """Processa a NF enviando as imagens para a API da Groq.

        Args:
            conteudo_arquivo (bytes): Conteúdo binário da imagem ou PDF.
            nome_arquivo (str): Nome original do arquivo.

        Returns:
            DadosDANFE: Modelo preenchido com as informações extraídas.

        Raises:
            ValueError: Se a GROQ_API_KEY não estiver configurada.
        """
        if not self.api_key:
            raise ValueError("Configure GROQ_API_KEY no arquivo .env para utilizar o extrator Groq.")

        prompt = self._obter_prompt_instrucao()
        extensao = nome_arquivo.lower().split(".")[-1]

        # Converte PDF em imagens JPEG ou otimiza (resolução reduzida para caber no limite do plano Groq)
        if extensao == "pdf":
            lista_imagens = self._converter_pdf_para_imagens(conteudo_arquivo, dpi=72)
        else:
            lista_imagens = [self._otimizar_imagem_bytes(conteudo_arquivo, max_dimensao=800)]

        conteudo_requisicao = [{"type": "text", "text": prompt}]

        for imagem_bytes in lista_imagens:
            # Reotimiza cada imagem do PDF para garantir tamanho mínimo
            imagem_otimizada = self._otimizar_imagem_bytes(imagem_bytes, max_dimensao=800)
            base64_imagem = base64.b64encode(imagem_otimizada).decode("utf-8")
            conteudo_requisicao.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_imagem}"
                }
            })

        # Utiliza o cliente OpenAI apontando para a URL da Groq
        cliente = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        )

        try:
            resposta = await cliente.chat.completions.create(
                model=self.nome_modelo,
                messages=[
                    {"role": "user", "content": conteudo_requisicao}
                ],
                temperature=0.1,
                max_tokens=16384,
                extra_body={"reasoning_format": "hidden"}
            )
            
            texto_resposta = resposta.choices[0].message.content
            dados_dict = self._limpar_e_converter_json(texto_resposta)
            return DadosDANFE(**dados_dict)

        except Exception as erro:
            raise ValueError(f"Falha ao extrair dados via Groq: {str(erro)}")
