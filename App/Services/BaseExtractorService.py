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
        from PIL import Image
        import io

        imagens_bytes: List[bytes] = []
        documento_pdf = pymupdf.open(stream=conteudo_pdf, filetype="pdf")

        paginas_pil = []
        for numero_pagina in range(len(documento_pdf)):
            pagina = documento_pdf.load_page(numero_pagina)
            zoom = dpi / 72
            matriz = pymupdf.Matrix(zoom, zoom)
            pixmap = pagina.get_pixmap(matrix=matriz, alpha=False)
            
            img_pil = Image.open(io.BytesIO(pixmap.tobytes("jpeg", jpg_quality=85)))
            paginas_pil.append(img_pil)

        documento_pdf.close()

        if not paginas_pil:
            return []

        # Calcula a altura total e a largura maxima
        largura_total = max(img.width for img in paginas_pil)
        altura_total = sum(img.height for img in paginas_pil)

        # Cria uma nova imagem combinada (fundo branco)
        imagem_combinada = Image.new("RGB", (largura_total, altura_total), (255, 255, 255))
        
        y_offset = 0
        for img in paginas_pil:
            imagem_combinada.paste(img, (0, y_offset))
            y_offset += img.height

        # Salva a imagem combinada em bytes
        buffer = io.BytesIO()
        imagem_combinada.save(buffer, format="JPEG", quality=85)
        return [buffer.getvalue()]

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
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texto_limpo, re.DOTALL)
        if match:
            texto_limpo = match.group(1).strip()

        try:
            parsed = json.loads(texto_limpo)
            if not isinstance(parsed, dict):
                raise ValueError(f"O JSON retornado não é um objeto/dicionário. Tipo retornado: {type(parsed)}")
            
            # Aplica mecânica de reconferência e sanitização automática
            parsed = self._validar_e_corrigir_extracao(parsed)
            return parsed
        except json.JSONDecodeError as erro:
            raise ValueError(f"Falha ao decodificar JSON retornado pelo modelo: {str(erro)}. Conteúdo bruto: {texto_resposta}")

    def _validar_e_corrigir_extracao(self, dados: dict) -> dict:
        """Mecânica de reconferência programática e auto-correção dos dados extraídos.
        Garante que CNPJs, Notas Fiscais NFO/NFD e quantidades estejam no padrão correto.
        """
        notas = dados.get("notaFiscalList", [])
        dados["quantidade_nota"] = len(notas)

        for nota in notas:
            rem = nota.get("Remetente", {})
            dest = nota.get("Destinatario", {})
            nfo = nota.get("NFO", {})
            nfd = nota.get("NFD", {})

            # 1. Sanitização de CNPJ (manter apenas números)
            if rem.get("cnpj"):
                rem["cnpj"] = re.sub(r"\D", "", str(rem["cnpj"]))
            if dest.get("cnpj"):
                dest["cnpj"] = re.sub(r"\D", "", str(dest["cnpj"]))

            # 2. Impedir que Inscrições Estaduais ou códigos estranhos virem número de nota
            for bloco in (nfo, nfd):
                num = str(bloco.get("numero", "")).strip()
                if len(num) > 9:  # Número de DANFE/NF tem no máximo 9 dígitos
                    bloco["numero"] = ""

        return dados

    def _preencher_metadados_arquivo(self, dados: dict, nome_arquivo: str, tamanho_bytes: int) -> dict:
        """Preenche dinamicamente as informações do arquivo que não precisam passar por inferência da IA."""
        import time
        from pathlib import Path
        
        nome_p = Path(nome_arquivo)
        extensao = nome_p.suffix.lower()
        if not extensao and "." in nome_arquivo:
            extensao = f".{nome_arquivo.split('.')[-1].lower()}"
            
        tamanho_kb = f"{tamanho_bytes / 1024:.2f} KB"
        data_atual_formatada = time.strftime("%Y-%m-%d %H:%M:%S")
        
        dados["arquivo"] = nome_p.stem
        dados["extensao"] = extensao
        dados["tamanho"] = tamanho_kb
        dados["data_criacao"] = data_atual_formatada
        
        return dados

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
        """Retorna o prompt padronizado e compacto direcionando a IA para extrair as notas na nova estrutura universal."""
        return """Examine este documento de Nota Fiscal (DANFE) ou DACTE.
Extraia os dados das notas e retorne APENAS um JSON no formato abaixo (sem markdown ou textos adicionais):

Formato esperado:
{"notaFiscalList":[{"Remetente":{"nome":"","cnpj":"","cep":"","endereco":"","cidade":"","uf":"","bairro":"","numero":""},"Destinatario":{"nome":"","cnpj":"","cep":"","endereco":"","cidade":"","uf":"","bairro":"","numero":""},"NFO":{"numero":"","serie":"","data":"","peso":0.0,"volume":0.0,"valor":0.0},"NFD":{"numero":"","serie":"","data":"","peso":0.0,"volume":0.0,"valor":0.0},"pedido":""}]}

REGRAS ESTRITAS DE EXTRAÇÃO E CONFERÊNCIA:
1. ENTIDADES (REMETENTE vs DESTINATÁRIO):
   - REMETENTE (Emitente da DANFE): É quem está emitindo o documento no TOPO ESQUERDO (ex: "SC DISTRIBUICAO LTDA"). O CNPJ do Remetente é o "CNPJ" impresso no topo da DANFE (ex: 01.206.820/0015-00). CUIDADO PARA NÃO INVERTER O CNPJ DO REMETENTE COM O DO DESTINATÁRIO!
   - DESTINATÁRIO: É a empresa descrita no quadro "DESTINATÁRIO / REMETENTE" (ex: "RANBAXY FARMACEUTICA LTDA"). O CNPJ do Destinatário está no campo "CNPJ/CPF" desse quadro (ex: 73.663.650/0004-33).

2. DIVISÃO DAS NOTAS (NFO vs NFD):
   - A NOTA PRINCIPAL do documento impresso no TOPO/CABEÇALHO (quadro "Nº", ex: 2939107, série 2) deve ser colocada no bloco **NFO** (Nota Fiscal Original).
   - A NOTA REFERENCIADA descrita no quadro "DADOS ADICIONAIS / INFORMAÇÕES COMPLEMENTARES" (ex: "Dev. Ref. NF(s). 000033759 de 11/04/2024") deve ser colocada no bloco **NFD** (Nota Fiscal de Devolução).

3. VALOR TOTAL E PESO:
   - "valor": Use o campo "VALOR TOTAL DA NOTA" (ex: 73.10) do quadro CÁLCULO DO IMPOSTO. NUNCA use valor total dos produtos nem Inscrição Estadual.
   - "peso" e "volume": Extraia do quadro TRANSPORTADOR/VOLUMES TRANSPORTADOS.

4. DADOS NUMÉRICOS:
   - CNPJ e CEP contêm APENAS DÍGITOS NÚMEROS. Formate o valor com ponto decimal."""
