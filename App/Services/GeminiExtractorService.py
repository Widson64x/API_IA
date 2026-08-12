"""Implementação do extrator de DANFE utilizando o modelo Google Gemini (Gemini Flash).

Utiliza o SDK oficial do Google GenAI para processamento nativo de imagens e documentos PDF.
"""

from App.Core.Config import configuracao
from App.Schemas.DanfeSchema import DadosDANFE
from App.Services.BaseExtractorService import DANFEExtratorBase


class ExtratorGemini(DANFEExtratorBase):
    """Extrator de dados de DANFE utilizando a API da Google Gemini.

    Attributes:
        nome_modelo (str): Identificador do modelo Gemini a ser utilizado.
    """

    def __init__(self, nome_modelo: str = "gemini-1.5-flash"):
        """Inicializa a classe do extrator Gemini.

        Args:
            nome_modelo (str): Identificador do modelo Gemini. Padrão 'gemini-1.5-flash'.
        """
        self.nome_modelo = nome_modelo
        self.api_key = configuracao.GEMINI_API_KEY

    async def extrair_dados(self, conteudo_arquivo: bytes, nome_arquivo: str) -> DadosDANFE:
        """Processa o documento enviado chamando a API do Gemini com fallback automático de modelos.

        Args:
            conteudo_arquivo (bytes): Conteúdo binário do arquivo PDF ou Imagem.
            nome_arquivo (str): Nome original do arquivo.

        Returns:
            DadosDANFE: Instância Pydantic com os dados parseados.

        Raises:
            ValueError: Em caso de falha na autenticação ou parsing do JSON.
        """
        if not self.api_key:
            raise ValueError("A chave GEMINI_API_KEY não foi configurada no arquivo .env")

        prompt = self._obter_prompt_instrucao()
        extensao = nome_arquivo.lower().split(".")[-1]
        mime_type = "application/pdf" if extensao == "pdf" else f"image/{extensao if extensao != 'jpg' else 'jpeg'}"

        modelos_tentativa = [self.nome_modelo, "gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro", "gemini-2.0-flash-exp", "gemini-2.0-flash", "gemini-2.5-flash"]
        modelos_unicos = []
        for m in modelos_tentativa:
            if m not in modelos_unicos:
                modelos_unicos.append(m)

        erros_detalhados = []

        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=self.api_key)

        # Tenta listar os modelos realmente disponíveis para esta chave de API
        try:
            modelos_remotos = [m.name.replace("models/", "") for m in cliente.models.list() if "generateContent" in getattr(m, "supported_generation_methods", [])]
            if modelos_remotos:
                for mr in modelos_remotos:
                    if mr not in modelos_unicos:
                        modelos_unicos.insert(0, mr)
        except Exception:
            pass

        for modelo_atual in modelos_unicos:
            try:
                parte_documento = types.Part.from_bytes(
                    data=conteudo_arquivo,
                    mime_type=mime_type,
                )

                resposta = await cliente.aio.models.generate_content(
                    model=modelo_atual,
                    contents=[parte_documento, prompt]
                )
                texto_resposta = resposta.text
                dados_dict = self._limpar_e_converter_json(texto_resposta)
                return DadosDANFE(**dados_dict)

            except Exception as erro:
                erro_str = str(erro)
                erros_detalhados.append(f"[{modelo_atual}]: {erro_str}")
                if any(k in erro_str.lower() for k in ["resource_exhausted", "429", "quota", "not_found", "not found", "404", "unavailable"]):
                    continue
                else:
                    raise erro

        resumo_erros = " | ".join(erros_detalhados[:3])
        raise ValueError(
            f"A chave do Google AI Studio retornou Cota Zero (RESOURCE_EXHAUSTED / Limit: 0). "
            f"O projeto exige vincular faturamento no Google AI Studio (Nível gratuito). "
            f"Erros observados: {resumo_erros}"
        )
