"""Implementação do extrator de DANFE utilizando DeepSeek / OpenRouter.

Permite integração direta com a API da DeepSeek ou roteamento via OpenRouter
(excelente opção para utilização de camadas gratuitas e testes de assertividade).
"""

import base64
import httpx
from typing import List
from openai import AsyncOpenAI

from App.Core.Config import configuracao
from App.Schemas.DanfeSchema import DadosDANFE
from App.Services.BaseExtractorService import DANFEExtratorBase


class ExtratorDeepSeek(DANFEExtratorBase):
    """Extrator de dados de DANFE utilizando a API DeepSeek / OpenRouter.

    Attributes:
        nome_modelo (str): Identificador do modelo (ex: deepseek-chat, openrouter-free).
    """

    def __init__(self, nome_modelo: str = "deepseek-chat"):
        """Inicializa o extrator DeepSeek.

        Args:
            nome_modelo (str): Identificador do modelo DeepSeek ou OpenRouter.
        """
        self.nome_modelo = nome_modelo
        self.api_key = configuracao.DEEPSEEK_API_KEY or configuracao.OPENROUTER_API_KEY

    async def _obter_modelos_gratuitos_visao_openrouter(self) -> List[str]:
        """Consulta a API do OpenRouter em tempo real para obter modelos de visão 100% gratuitos ativos.

        Returns:
            List[str]: Lista contendo os identificadores dos modelos de visão com custo zero.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client_http:
                resposta = await client_http.get("https://openrouter.ai/api/v1/models")
                if resposta.status_code == 200:
                    dados = resposta.json()
                    modelos_gratuitos = []
                    for item in dados.get("data", []):
                        m_id = item.get("id", "")
                        pricing = item.get("pricing", {})
                        modalities = item.get("architecture", {}).get("input_modalities", [])
                        
                        eh_gratuito = ":free" in m_id or (str(pricing.get("prompt")) == "0" and str(pricing.get("completion")) == "0")
                        tem_visao = "image" in modalities or "file" in modalities
                        
                        if eh_gratuito and tem_visao:
                            modelos_gratuitos.append(m_id)
                    
                    if modelos_gratuitos:
                        return modelos_gratuitos
        except Exception:
            pass

        # Fallback de segurança caso a listagem dinâmica falhe
        return ["google/gemini-2.0-flash-exp:free", "qwen/qwen-2.5-vl-72b-instruct:free", "meta-llama/llama-3.2-11b-vision-instruct:free"]

    async def extrair_dados(self, conteudo_arquivo: bytes, nome_arquivo: str) -> DadosDANFE:
        """Processa a DANFE enviando as imagens para a API da DeepSeek ou OpenRouter.

        Args:
            conteudo_arquivo (bytes): Conteúdo binário da imagem ou PDF.
            nome_arquivo (str): Nome original do arquivo.

        Returns:
            DadosDANFE: Modelo Pydantic preenchido com as informações extraídas.

        Raises:
            ValueError: Se nem DEEPSEEK_API_KEY nem OPENROUTER_API_KEY estiverem configuradas.
        """
        if not self.api_key:
            raise ValueError("Configure DEEPSEEK_API_KEY ou OPENROUTER_API_KEY no arquivo .env para utilizar este extrator")

        prompt = self._obter_prompt_instrucao()
        extensao = nome_arquivo.lower().split(".")[-1]

        # Define se usaremos OpenRouter ou DeepSeek Direto
        usar_openrouter = (
            bool(configuracao.OPENROUTER_API_KEY) or 
            "openrouter" in self.nome_modelo or 
            ":free" in self.nome_modelo or 
            not configuracao.DEEPSEEK_API_KEY
        )

        if usar_openrouter:
            base_url = "https://openrouter.ai/api/v1"
            api_key = configuracao.OPENROUTER_API_KEY or "sk-or-v1-anonymous"
            headers_extra = {
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "IDocs_IA DANFE Extractor"
            }
            if self.nome_modelo in ("openrouter-free", "deepseek-chat", "deepseek", "openrouter"):
                modelos_tentativa = await self._obter_modelos_gratuitos_visao_openrouter()
            else:
                modelos_tentativa = [self.nome_modelo]
        else:
            base_url = "https://api.deepseek.com"
            api_key = configuracao.DEEPSEEK_API_KEY
            headers_extra = {}
            modelos_tentativa = [self.nome_modelo]

        # Converte PDF em imagens JPEG compactas ou otimiza imagem existente
        if extensao == "pdf":
            lista_imagens = self._converter_pdf_para_imagens(conteudo_arquivo)
        else:
            lista_imagens = [self._otimizar_imagem_bytes(conteudo_arquivo)]

        conteudo_requisicao = [{"type": "text", "text": prompt}]

        for imagem_bytes in lista_imagens:
            base64_imagem = base64.b64encode(imagem_bytes).decode("utf-8")
            conteudo_requisicao.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_imagem}"
                }
            })

        cliente = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=headers_extra if headers_extra else None
        )

        erros_observados = []
        print(f"\n[OpenRouter] Modelos de visão gratuitos detectados ({len(modelos_tentativa)}): {modelos_tentativa}")

        for modelo_atual in modelos_tentativa:
            print(f"[OpenRouter] Tentando modelo: '{modelo_atual}'...")
            try:
                resposta = await cliente.chat.completions.create(
                    model=modelo_atual,
                    messages=[
                        {"role": "user", "content": conteudo_requisicao}
                    ],
                    temperature=0.1,
                    timeout=35.0  # Limita a espera em 35s por modelo para não travar a fila do cliente
                )

                texto_resposta = resposta.choices[0].message.content
                dados_dict = self._limpar_e_converter_json(texto_resposta)
                print(f"[OpenRouter] Sucesso com o modelo: '{modelo_atual}'")
                return DadosDANFE(**dados_dict)

            except Exception as erro:
                print(f"[OpenRouter] Falha/Timeout no modelo '{modelo_atual}': {str(erro)}")
                erros_observados.append(f"[{modelo_atual}]: {str(erro)}")
                continue

        raise ValueError(
            f"Falha ao extrair dados via OpenRouter. Erros: {' | '.join(erros_observados[:2])}. "
            f"Verifique se você inseriu uma chave válida em OPENROUTER_API_KEY no arquivo .env "
            f"(Você pode gerar uma chave 100% gratuita em https://openrouter.ai/keys)."
        )
