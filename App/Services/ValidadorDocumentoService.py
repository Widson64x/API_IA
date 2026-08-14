"""Serviço de validação prévia e triagem inteligente de documentos (Guarda de Tokens).

Executa validações rápidas locais (em CPU, sem qualquer chamada de API ou custo de tokens)
para barrar arquivos vazios, corrompidos, páginas em branco ou documentos irrelevantes/não-fiscais
antes de invocar os modelos de Inteligência Artificial.
"""

import io
import unicodedata
from typing import Tuple
from PIL import Image, ImageStat
import pymupdf


class ValidadorDocumentoService:
    """Validador heurístico e estrutural de documentos fiscais."""

    # Conjunto de palavras-chave fiscais e de transporte
    _TERMOS_FISCAIS = (
        "danfe", "dacte", "nfe", "nf-e", "cte", "ct-e",
        "nota fiscal", "conhecimento de transporte", "chave de acesso",
        "natureza da operacao", "natureza da operacao",
        "protocolo de autorizacao", "protocolo de autorizacao",
        "remetente", "destinatario", "emitente",
        "inscricao estadual", "cnpj", "cpf", "valor total",
        "base de calculo", "icms", "issqn", "dados do produto",
        "dados dos produtos", "duplicata", "fatura", "transportador",
        "documento auxiliar", "informacoes complementares", "pedido",
        "dados adicionais"
    )

    @classmethod
    def _normalizar_texto(cls, texto: str) -> str:
        """Remove acentos e converte para minúsculas para facilitar a busca heurística."""
        texto_sem_acento = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII")
        return texto_sem_acento.lower()

    @classmethod
    def validar_documento(cls, conteudo_arquivo: bytes, nome_arquivo: str) -> Tuple[bool, str]:
        """Realiza a triagem completa do documento sem consumir tokens de IA.

        Args:
            conteudo_arquivo (bytes): Conteúdo binário do arquivo.
            nome_arquivo (str): Nome do arquivo com extensão.

        Returns:
            Tuple[bool, str]: (valido: bool, mensagem_ou_diagnostico: str)

        Raises:
            ValueError: Se o arquivo for inválido, vazio, corrompido ou irrelevante.
        """
        # 1. Checagem de Tamanho Mínimo
        if not conteudo_arquivo or len(conteudo_arquivo) < 64:
            raise ValueError(
                "O arquivo enviado está vazio (0 bytes) ou possui tamanho insuficiente para ser um documento legível."
            )

        extensao = nome_arquivo.lower().split(".")[-1]

        # 2. Validação para Arquivos PDF
        if extensao == "pdf":
            cls._validar_pdf(conteudo_arquivo, nome_arquivo)
        else:
            # 3. Validação para Arquivos de Imagem (PNG, JPG, JPEG, WEBP)
            cls._validar_imagem(conteudo_arquivo, nome_arquivo)

        return True, "Documento validado com sucesso para processamento por IA."

    @classmethod
    def _validar_pdf(cls, conteudo_arquivo: bytes, nome_arquivo: str) -> None:
        """Verifica a integridade e relevância fiscal de um arquivo PDF."""
        try:
            documento = pymupdf.open(stream=conteudo_arquivo, filetype="pdf")
        except Exception as e:
            raise ValueError(f"Não foi possível abrir o arquivo PDF '{nome_arquivo}'. O arquivo está corrompido ou em formato inválido.")

        total_paginas = len(documento)
        if total_paginas == 0:
            documento.close()
            raise ValueError(f"O arquivo PDF '{nome_arquivo}' não possui páginas válidas para leitura.")

        # Extrai texto de todas as páginas para análise
        texto_completo = ""
        for num_pag in range(total_paginas):
            pagina = documento.load_page(num_pag)
            texto_completo += pagina.get_text() + "\n"

        documento.close()

        texto_limpo = texto_completo.strip()

        # Se o PDF contém camada de texto pesquisável (mais de 50 caracteres)
        if len(texto_limpo) >= 50:
            texto_normalizado = cls._normalizar_texto(texto_limpo)

            # Verifica se pelo menos um termo fiscal essencial está presente
            encontrou_termo_fiscal = any(termo in texto_normalizado for termo in cls._TERMOS_FISCAIS)

            if not encontrou_termo_fiscal:
                raise ValueError(
                    f"O arquivo PDF '{nome_arquivo}' contém texto legível, mas não foi identificado como um documento fiscal "
                    f"(nenhum termo como DANFE, DACTE, Nota Fiscal, CNPJ ou ICMS foi localizado). "
                    f"O processamento foi interrompido para economizar recursos e evitar consumo desnecessário de tokens de IA."
                )

    @classmethod
    def _validar_imagem(cls, conteudo_arquivo: bytes, nome_arquivo: str) -> None:
        """Verifica a integridade e legibilidade básica de arquivos de imagem."""
        try:
            imagem = Image.open(io.BytesIO(conteudo_arquivo))
            imagem.verify()
        except Exception as e:
            raise ValueError(f"O arquivo de imagem '{nome_arquivo}' está corrompido ou em formato não suportado.")

        # Reabre após verify()
        imagem = Image.open(io.BytesIO(conteudo_arquivo))
        largura, altura = imagem.size

        if largura < 50 or altura < 50:
            raise ValueError(
                f"A imagem '{nome_arquivo}' possui dimensões muito reduzidas ({largura}x{altura}px) "
                f"para conter uma Nota Fiscal legível."
            )

        # Checa se a imagem é completamente uniforme (ex: 100% branca ou 100% preta)
        try:
            stat = ImageStat.Stat(imagem.convert("L"))
            desvio_padrao = stat.stddev[0] if stat.stddev else 0.0
            if desvio_padrao < 0.5:
                raise ValueError(
                    f"A imagem '{nome_arquivo}' parece ser uma imagem em branco ou uniforme sem conteúdo legível."
                )
        except ValueError:
            raise
        except Exception:
            pass  # Prossegue caso a checagem estatística não seja conclusiva
