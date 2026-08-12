"""Implementação do extrator de NF utilizando OpenRouter.

Permite integração direta com a API do OpenRouter
(excelente opção para utilização de camadas gratuitas e testes de assertividade).
"""

import base64
import httpx
from typing import List
from openai import AsyncOpenAI

from App.Core.Config import configuracao
from App.Schemas.DanfeSchema import DadosDANFE
from App.Services.BaseExtractorService import DANFEExtratorBase


class ExtratorOpenRouter(DANFEExtratorBase):
    """Extrator de dados de NF utilizando a API OpenRouter.

    Attributes:
        nome_modelo (str): Identificador do modelo (ex: openrouter-free, qwen/qwen-2.5-vl-72b-instruct:free).
    """

    def __init__(self, nome_modelo: str = "openrouter-free"):
        """Inicializa o extrator OpenRouter.

        Args:
            nome_modelo (str): Identificador do modelo OpenRouter.
        """
        self.nome_modelo = nome_modelo
        self.api_key = configuracao.OPENROUTER_API_KEY

    async def _obter_modelos_gratuitos_visao_openrouter(self) -> List[str]:
        """Consulta a API do OpenRouter em tempo real para obter modelos de visão 100% gratuitos ativos.

        Returns:
            List[str]: Lista contendo os identificadores dos modelos de visão com custo zero.
        """
        # Desabilitando a busca dinâmica temporariamente pois o OpenRouter está retornando 
        # modelos em fase de teste (Nvidia/Lyria) que estão dando timeout/502.
        # Vamos direto para o fallback que contém o modelo que funcionava antes.
        '''
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
        '''

        # Fallback de segurança usando o modelo original do repositório GitHub
        return ["google/gemini-2.0-flash-exp:free", "google/gemini-2.0-flash-lite-preview-02-05:free", "qwen/qwen-2.5-vl-72b-instruct:free"]

    async def extrair_dados(self, conteudo_arquivo: bytes, nome_arquivo: str) -> DadosDANFE:
        """Processa a NF enviando as imagens para a API do OpenRouter.

        Args:
            conteudo_arquivo (bytes): Conteúdo binário da imagem ou PDF.
            nome_arquivo (str): Nome original do arquivo.

        Returns:
            DadosDANFE: Modelo Pydantic preenchido com as informações extraídas.

        Raises:
            ValueError: Se OPENROUTER_API_KEY não estiver configurada.
        """
        if not self.api_key:
            raise ValueError("Configure OPENROUTER_API_KEY no arquivo .env para utilizar este extrator")

        prompt = self._obter_prompt_instrucao()
        extensao = nome_arquivo.lower().split(".")[-1]

        base_url = "https://openrouter.ai/api/v1"
        headers_extra = {
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "IDocs_IA NF Extractor"
        }
        
        if self.nome_modelo in ("openrouter-free", "openrouter"):
            modelos_tentativa = await self._obter_modelos_gratuitos_visao_openrouter()
        else:
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
            api_key=self.api_key,
            base_url=base_url,
            default_headers=headers_extra
        )

        erros_observados = []
        print(f"\n[OpenRouter] Modelos de visão detectados ({len(modelos_tentativa)}): {modelos_tentativa}")
        print("[OpenRouter] Aviso: Alguns modelos gratuitos podem estar fora do ar e gerar erro. O sistema tentará o próximo automaticamente. Por favor, aguarde e não cancele...")

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
        )
