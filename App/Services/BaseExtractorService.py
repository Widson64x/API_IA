"""Classe base abstrata para a estratégia de extração de dados de DANFE.

Define a interface comum para todos os extratores baseados em modelos de IA
(Gemini, OpenAI, Claude, DeepSeek) e fornece métodos auxiliares reutilizáveis
para conversão de arquivos PDF e higienização de respostas em formato JSON.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import List
import pymupdf  # PyMuPDF nativo para alta performance

from App.Schemas.DanfeSchema import DadosDANFE


class DANFEExtratorBase(ABC):
    """Classe base abstrata para extratores de DANFE.

    Atua como contrato para todas as implementações concretas de extratores,
    garantindo polimorfismo no consumo da API.
    """

    @abstractmethod
    async def extrair_dados(self, conteudo_arquivo: bytes, nome_arquivo: str) -> DadosDANFE:
        """Método abstrato que deve ser implementado por cada modelo de IA.

        Args:
            conteudo_arquivo (bytes): Conteúdo binário do arquivo (imagem ou PDF).
            nome_arquivo (str): Nome do arquivo enviado para identificação da extensão.

        Returns:
            DadosDANFE: Objeto Pydantic preenchido com os dados extraídos da nota.
        """
        pass

    def _converter_pdf_para_imagens(self, conteudo_pdf: bytes, dpi: int = 140) -> List[bytes]:
        """Converte as páginas de um arquivo PDF em uma lista de imagens JPEG compactadas.

        Utiliza a biblioteca PyMuPDF (pymupdf) configurada para gerar arquivos JPEG otimizados,
        reduzindo em até 95% o tamanho do payload enviado aos modelos de IA.

        Args:
            conteudo_pdf (bytes): Conteúdo binário do PDF.
            dpi (int): Resolução da imagem convertida (padrão: 140 DPI para balanço ideal velocidade/OCR).

        Returns:
            List[bytes]: Lista contendo os bytes das imagens JPEG renderizadas de cada página.
        """
        imagens_bytes: List[bytes] = []
        documento_pdf = pymupdf.open(stream=conteudo_pdf, filetype="pdf")

        for numero_pagina in range(len(documento_pdf)):
            pagina = documento_pdf.load_page(numero_pagina)
            zoom = dpi / 72
            matriz = pymupdf.Matrix(zoom, zoom)
            pixmap = pagina.get_pixmap(matrix=matriz, alpha=False)
            imagens_bytes.append(pixmap.tobytes("jpeg", jpg_quality=85))

        documento_pdf.close()
        return imagens_bytes

    def _limpar_e_converter_json(self, texto_resposta: str) -> dict:
        """Remove marcadores de bloco de código Markdown (```json ... ```) e converte o texto para dict.

        Args:
            texto_resposta (str): Resposta bruta retornada pela API do modelo de IA.

        Returns:
            dict: Dicionário contendo os dados extraídos.

        Raises:
            ValueError: Caso a resposta não possa ser serializada como JSON válido.
        """
        texto_limpo = texto_resposta.strip()

        # Remove blocos de raciocínio/thinking de modelos com modo reasoning (ex: Qwen 3.6)
        # Trata tanto blocos fechados (<think>...</think>) quanto não fechados (<think>... sem </think>)
        texto_limpo = re.sub(r"<think>[\s\S]*?</think>", "", texto_limpo).strip()
        texto_limpo = re.sub(r"<think>[\s\S]*", "", texto_limpo).strip()
        
        # Remove delimitadores de código markdown comuns retornado por LLMs
        padrao_markdown = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(padrao_markdown, texto_limpo)
        if match:
            texto_limpo = match.group(1).strip()

        try:
            return json.loads(texto_limpo)
        except json.JSONDecodeError as erro:
            raise ValueError(f"Falha ao decodificar JSON retornado pelo modelo: {str(erro)}. Conteúdo bruto: {texto_resposta}")

    def _otimizar_imagem_bytes(self, conteudo_imagem: bytes, max_dimensao: int = 1400) -> bytes:
        """Redimensiona e comprime imagens de alta resolução (ex: fotos de celular/WhatsApp)
        para garantir payload leve e evitar erros de Read Timeout na API.

        Args:
            conteudo_imagem (bytes): Conteúdo binário da imagem original.
            max_dimensao (int): Limite máximo para a maior dimensão da imagem em pixels.

        Returns:
            bytes: Imagem JPEG comprimida em memória.
        """
        try:
            import io
            from PIL import Image

            imagem = Image.open(io.BytesIO(conteudo_imagem))
            imagem = imagem.convert("RGB")
            
            largura, altura = imagem.size
            if max(largura, altura) > max_dimensao:
                proporcao = max_dimensao / float(max(largura, altura))
                nova_largura = int(largura * proporcao)
                nova_altura = int(altura * proporcao)
                imagem = imagem.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
                
            buffer = io.BytesIO()
            imagem.save(buffer, format="JPEG", quality=80, optimize=True)
            return buffer.getvalue()
        except Exception:
            return conteudo_imagem

    def _obter_prompt_instrucao(self) -> str:
        """Retorna o prompt padronizado e compacto direcionando a IA para extrair as notas de devolução.

        Returns:
            str: Instrução minificada garantindo foco na extração dos dados de origem, destino e valores.
        """
        return """Examine este documento (PDF/Imagem) contendo notas fiscais. Extraia com precisão os dados de origem, destino e valores das notas (focando em devoluções/importação). Retorne APENAS um JSON compacto (sem markdown e sem crases de bloco de código):
{"arquivo":"","extensao":"","tamanho":"","data_criacao":"","quantidade_nota":0,"notaFiscalList":[{"origem_nome":"","origem_cnpj":"","origem_cep":"","origem_endereco":"","origem_cidade":"","origem_uf":"","origem_bairro":"","origem_numero":"","destino_nome":"","destino_cnpj":"","destino_cep":"","destino_endereco":"","destino_cidade":"","destino_uf":"","destino_bairro":"","destino_numero":"","devolucao_nota":"","devolucao_serie":"","origem_nota":"","origem_serie":"","origem_data":"","pedido":"","devolucao_peso":0.0,"devolucao_volume":0.0,"devolucao_valor":0.0}]}
REGRAS: 
- O campo arquivo, extensao, tamanho e data_criacao podem ficar vazios ou nulos caso não encontre no documento, o sistema os preencherá depois.
- Para cada nota no documento, crie um item em notaFiscalList. 
- Extraia corretamente cnpj (apenas numeros) e cep (apenas numeros).
- Atente-se para identificar qual é a nota de devolução e qual é a nota de origem."""
