"""Implementação do extrator de DANFE utilizando o modelo Mistral AI (La Plateforme).

Utiliza a API compatível com OpenAI da Mistral para inferência rápida e barata usando modelos
como o pixtral-12b que tem 128k de contexto e visão nativa.
"""

import base64
from App.Core.Config import configuracao
from App.Schemas.DanfeSchema import DadosDANFE
from App.Services.BaseExtractorService import DANFEExtratorBase
from openai import AsyncOpenAI


class ExtratorMistral(DANFEExtratorBase):
    """Extrator de dados de DANFE utilizando a API da Mistral AI.

    Attributes:
        nome_modelo (str): Identificador do modelo Mistral a ser utilizado.
    """

    def __init__(self, nome_modelo: str = "pixtral-12b-2409"):
        """Inicializa a classe do extrator Mistral AI.

        Args:
            nome_modelo (str): Identificador do modelo Mistral. Padrão 'pixtral-12b-2409'.
        """
        self.nome_modelo = nome_modelo
        self.api_key = configuracao.MISTRAL_API_KEY

    async def extrair_dados(self, conteudo_arquivo: bytes, nome_arquivo: str) -> DadosDANFE:
        """Processa a NF enviando as imagens para a API da Mistral AI.

        Args:
            conteudo_arquivo (bytes): Conteúdo binário da imagem ou PDF.
            nome_arquivo (str): Nome original do arquivo.

        Returns:
            DadosDANFE: Modelo Pydantic preenchido com as informações extraídas.

        Raises:
            ValueError: Se MISTRAL_API_KEY não estiver configurada.
        """
        if not self.api_key:
            raise ValueError("Configure MISTRAL_API_KEY no arquivo .env para utilizar este extrator")

        prompt = self._obter_prompt_instrucao()
        extensao = nome_arquivo.lower().split(".")[-1]

        base_url = "https://api.mistral.ai/v1"
        
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
                print(f"[DEBUG MISTRAL] Falha ao extrair texto do PDF: {e}")
            
            lista_imagens = self._converter_pdf_para_imagens(conteudo_arquivo)
        else:
            lista_imagens = [self._otimizar_imagem_bytes(conteudo_arquivo)]

        prompt_enviado = prompt
        if texto_pdf.strip():
            prompt_enviado += f"\n\n--- TEXTO EXTRAÍDO DO DOCUMENTO PARA FACILITAR A LEITURA ---\n{texto_pdf}"

        # Prepara o payload para o modelo
        req_atual = [{"type": "text", "text": prompt_enviado}]
        
        for imagem_bytes in lista_imagens:
            base64_imagem = base64.b64encode(imagem_bytes).decode("utf-8")
            req_atual.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_imagem}"
                }
            })

        print(f"[DEBUG MISTRAL] Instanciando cliente AsyncOpenAI (base_url={base_url})...")
        cliente = AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url,
        )
        
        print(f"[DEBUG MISTRAL] Disparando request para modelo: '{self.nome_modelo}'... (Timeout 60s)")
        import time
        t0 = time.time()
        
        try:
            resposta = await cliente.chat.completions.create(
                model=self.nome_modelo,
                messages=[
                    {"role": "user", "content": req_atual}
                ],
                temperature=0.1,
                timeout=60.0
            )
            print(f"[DEBUG MISTRAL] Resposta recebida em {time.time() - t0:.2f}s do modelo '{self.nome_modelo}'")
            
            texto_resposta = resposta.choices[0].message.content
            print(f"[DEBUG MISTRAL] Texto da resposta recebida (Tamanho: {len(texto_resposta)} caracteres):\n{texto_resposta[:300]}...")
            
            print(f"[DEBUG MISTRAL] Iniciando parse JSON da resposta...")
            dados_dict = self._limpar_e_converter_json(texto_resposta)
            print(f"[DEBUG MISTRAL] Parse concluído com sucesso!")
            
            return DadosDANFE(**dados_dict)

        except Exception as erro:
            erro_str = str(erro)
            print(f"[DEBUG MISTRAL] Falha/Timeout no modelo '{self.nome_modelo}' após {time.time() - t0:.2f}s: {erro_str}")
            raise ValueError(f"Falha ao extrair dados via Mistral AI. Erro: {erro_str}. Verifique se você inseriu uma chave válida em MISTRAL_API_KEY no arquivo .env ")
