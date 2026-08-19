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

        texto_pdf = ""
        if extensao == "pdf":
            try:
                import pymupdf
                documento_pdf = pymupdf.open(stream=conteudo_arquivo, filetype="pdf")
                for pagina in documento_pdf:
                    texto_pdf += pagina.get_text() + "\n"
                documento_pdf.close()
            except Exception as e:
                print(f"[DEBUG GROQ] Falha ao extrair texto do PDF: {e}")

        # Se temos texto extraído com qualidade (sem caracteres corrompidos), usamos o LLaMA 3.3 70B Versatile
        tem_texto_limpo = bool(texto_pdf.strip() and len(texto_pdf) > 50 and "PÀGT" not in texto_pdf)

        modelos_tentativa = []
        if tem_texto_limpo:
            modelos_tentativa.append("llama-3.3-70b-versatile")
        
        # Modelo de visão da Groq (suporta imagem)
        modelos_tentativa.extend(["llama-3.2-11b-vision-preview", "llama-3.3-70b-versatile"])

        # Remove duplicados mantendo a ordem
        modelos_unicos = []
        for m in modelos_tentativa:
            if m not in modelos_unicos:
                modelos_unicos.append(m)

        cliente = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        )

        erros = []
        for modelo_atual in modelos_unicos:
            print(f"[DEBUG GROQ] Disparando requisição no modelo '{modelo_atual}'...")
            
            prompt_final = prompt
            if tem_texto_limpo:
                prompt_final += f"\n\n--- TEXTO DO DOCUMENTO ---\n{texto_pdf}"

            conteudo_requisicao = [{"type": "text", "text": prompt_final}]

            # Só envia imagem se o modelo for de visão
            if "vision" in modelo_atual:
                if extensao == "pdf":
                    lista_imagens = self._converter_pdf_para_imagens(conteudo_arquivo, dpi=72)
                else:
                    lista_imagens = [self._otimizar_imagem_bytes(conteudo_arquivo, max_dimensao=800)]

                for imagem_bytes in lista_imagens:
                    imagem_otimizada = self._otimizar_imagem_bytes(imagem_bytes, max_dimensao=800)
                    base64_imagem = base64.b64encode(imagem_otimizada).decode("utf-8")
                    conteudo_requisicao.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_imagem}"
                        }
                    })

            try:
                resposta = await cliente.chat.completions.create(
                    model=modelo_atual,
                    messages=[
                        {"role": "user", "content": conteudo_requisicao}
                    ],
                    temperature=0.1,
                    max_tokens=4096
                )
                
                texto_resposta = resposta.choices[0].message.content or ""
                dados_dict = self._limpar_e_converter_json(texto_resposta)
                dados_dict = self._preencher_metadados_arquivo(dados_dict, nome_arquivo, len(conteudo_arquivo))
                print(f"[DEBUG GROQ] Sucesso no modelo '{modelo_atual}'!")
                return DadosDANFE(**dados_dict)

            except Exception as erro:
                print(f"[DEBUG GROQ] Erro no modelo '{modelo_atual}': {erro}")
                erros.append(f"[{modelo_atual}]: {str(erro)}")
                continue

        raise ValueError(f"Falha ao extrair dados via Groq: {' | '.join(erros)}")
