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

    async def _obter_modelos_gratuitos_openrouter(self, tem_texto: bool = False) -> List[str]:
        """Consulta a API do OpenRouter em tempo real filtrando modelos ruins."""
        try:
            import httpx
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
                            if "llama" in m_id.lower() or "qwen" in m_id.lower() or "pixtral" in m_id.lower() or "vl" in m_id.lower():
                                modelos_gratuitos.append(m_id)
                        
                    if modelos_gratuitos:
                        return modelos_gratuitos
        except Exception:
            pass
        
        return [
            "qwen/qwen-2-vl-72b-instruct:free",
            "meta-llama/llama-3.2-90b-vision-instruct:free",
            "nvidia/nemotron-nano-12b-v2-vl:free"
        ]

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
        # Converte PDF em imagens JPEG compactas ou otimiza imagem existente
        texto_pdf = ""
        if extensao == "pdf":
            try:
                import pymupdf
                documento_pdf = pymupdf.open(stream=conteudo_arquivo, filetype="pdf")
                for pagina in documento_pdf:
                    texto_pdf += pagina.get_text() + "\n"
                documento_pdf.close()
            except Exception as e:
                print(f"[DEBUG OPENROUTER] Falha ao extrair texto do PDF: {e}")
            
            lista_imagens = self._converter_pdf_para_imagens(conteudo_arquivo)
        else:
            lista_imagens = [self._otimizar_imagem_bytes(conteudo_arquivo)]

        if self.nome_modelo in ("openrouter-free", "openrouter"):
            modelos_tentativa = await self._obter_modelos_gratuitos_openrouter(tem_texto=bool(texto_pdf.strip()))
        else:
            modelos_tentativa = [self.nome_modelo]

        prompt_enviado = prompt
        if texto_pdf.strip():
            prompt_enviado += f"\n\n--- TEXTO EXTRAÍDO DO DOCUMENTO PARA FACILITAR A LEITURA ---\n{texto_pdf}"

        print(f"[DEBUG OPENROUTER] Instanciando cliente AsyncOpenAI (base_url={base_url})...")
        cliente = AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url,
            default_headers=headers_extra,
            timeout=15.0  # Limite máximo absoluto (evita 300s de delay do cliente HTTP)
        )
        
        erros_observados = []
        print(f"\n[OpenRouter] Modelos detectados para tentativa ({len(modelos_tentativa)}): {modelos_tentativa}")
        print("[OpenRouter] Aviso: Alguns modelos gratuitos podem estar fora do ar. O sistema tentará o próximo automaticamente...")

        # Se conseguimos extrair texto, usaremos apenas texto para evitar que modelos não-visuais retornem erro 404/400.
        tem_texto_extraido = bool(texto_pdf.strip() and len(texto_pdf) > 50)

        for modelo_atual in modelos_tentativa:
            print(f"[DEBUG OPENROUTER] Disparando request para modelo: '{modelo_atual}'... (Timeout 60s)")
            import time
            t0 = time.time()
            
            # Prepara o payload para o modelo atual
            req_atual = [{"type": "text", "text": prompt_enviado}]
            
            # Como todos os modelos selecionados agora são multimodais (visão),
            # nós SEMPRE enviamos a imagem convertida em Base64 para garantir o OCR nativo deles!
            for imagem_bytes in lista_imagens:
                base64_imagem = base64.b64encode(imagem_bytes).decode("utf-8")
                req_atual.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_imagem}"
                    }
                })

            try:
                resposta = await cliente.chat.completions.create(
                    model=modelo_atual,
                    messages=[
                        {"role": "user", "content": req_atual}
                    ],
                    temperature=0.1,
                    timeout=60.0  # Limita a espera em 60s
                )
                print(f"[DEBUG OPENROUTER] Resposta recebida em {time.time() - t0:.2f}s do modelo '{modelo_atual}'")
                if not getattr(resposta, "choices", None):
                    raise ValueError(f"Resposta inválida ou vazia do modelo. Corpo: {resposta}")
                    
                texto_resposta = resposta.choices[0].message.content or ""
                print(f"[DEBUG OPENROUTER] Texto da resposta recebida (Tamanho: {len(texto_resposta)} caracteres):\n{texto_resposta[:300]}...")
                
                print(f"[DEBUG OPENROUTER] Iniciando parse JSON da resposta...")
                dados_dict = self._limpar_e_converter_json(texto_resposta)
                dados_dict = self._preencher_metadados_arquivo(dados_dict, nome_arquivo, len(conteudo_arquivo))
                print(f"[DEBUG OPENROUTER] Parse concluído com sucesso!")
                return DadosDANFE(**dados_dict)

            except Exception as erro:
                print(f"[DEBUG OPENROUTER] Falha/Timeout no modelo '{modelo_atual}' após {time.time() - t0:.2f}s: {str(erro)}")
                import traceback
                traceback.print_exc()
                erros_observados.append(f"[{modelo_atual}]: {str(erro)}")
                continue

        raise ValueError(
            f"Falha ao extrair dados via OpenRouter. Erros: {' | '.join(erros_observados[:2])}. "
            f"Verifique se você inseriu uma chave válida em OPENROUTER_API_KEY no arquivo .env "
        )
