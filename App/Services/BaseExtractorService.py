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

    def _converter_pdf_para_imagens(self, conteudo_pdf: bytes, dpi: int = 160) -> List[bytes]:
        """Converte as páginas de um arquivo PDF em uma lista de imagens JPEG compactadas.

        Cada página é renderizada e enviada como uma imagem individual para preservar
        a máxima resolução e legibilidade de OCR de dados detalhados (CEPs, Nomes, Números).

        Args:
            conteudo_pdf (bytes): Conteúdo binário do PDF.
            dpi (int): Resolução da imagem renderizada (padrão: 160 DPI).

        Returns:
            List[bytes]: Lista de bytes JPEG onde cada elemento corresponde a uma página do PDF.
        """
        from PIL import Image
        import io

        imagens_bytes: List[bytes] = []
        documento_pdf = pymupdf.open(stream=conteudo_pdf, filetype="pdf")

        for numero_pagina in range(len(documento_pdf)):
            pagina = documento_pdf.load_page(numero_pagina)
            zoom = dpi / 72
            matriz = pymupdf.Matrix(zoom, zoom)
            pixmap = pagina.get_pixmap(matrix=matriz, alpha=False)
            
            img_pil = Image.open(io.BytesIO(pixmap.tobytes("jpeg", jpg_quality=90)))
            
            buffer = io.BytesIO()
            img_pil.save(buffer, format="JPEG", quality=90, optimize=True)
            imagens_bytes.append(buffer.getvalue())

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

            # 1. Sanitização de CNPJ (manter apenas números e ignorar telefones capturados por engano)
            for entidade in (rem, dest):
                if entidade.get("cnpj"):
                    cnpj_limpo = re.sub(r"\D", "", str(entidade["cnpj"]))
                    # Se tiver 10 dígitos ou se não for um CNPJ/CPF com tamanho válido (14 ou 11 dígitos), limpa
                    if len(cnpj_limpo) == 10:
                        entidade["cnpj"] = ""
                    else:
                        entidade["cnpj"] = cnpj_limpo

            # 2. Impedir que Inscrições Estaduais ou códigos estranhos virem número de nota
            for bloco in (nfo, nfd):
                num = str(bloco.get("numero", "")).strip()
                if len(num) > 9:  # Número de DANFE/NF tem no máximo 9 dígitos
                    bloco["numero"] = ""

            # 3. Em notas de Devolução/Retorno, se NFO e NFD tiverem exatamente o mesmo número, limpa NFO para evitar duplicação incorreta
            pedido_str = str(nota.get("pedido", "")).upper()
            num_nfo = str(nfo.get("numero", "")).strip()
            num_nfd = str(nfd.get("numero", "")).strip()
            if num_nfo and num_nfd and num_nfo == num_nfd and any(k in pedido_str for k in ["DEVOL", "RETORNO"]):
                nfo["numero"] = ""

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
        return """Examine este documento, que pode ser uma Nota Fiscal (DANFE) ou um Conhecimento de Transporte (DACTE).
Extraia os dados das notas e retorne APENAS um JSON no formato abaixo (sem markdown ou textos adicionais):

Formato esperado:
{"arquivo":"","extensao":"","tamanho":"","data_criacao":"","quantidade_nota":1,"notaFiscalList":[{"Remetente":{"nome":"","cnpj":"","cep":"","endereco":"","cidade":"","uf":"","bairro":"","numero":""},"Destinatario":{"nome":"","cnpj":"","cep":"","endereco":"","cidade":"","uf":"","bairro":"","numero":""},"NFO":{"numero":"","serie":"","data":"","peso":0.0,"volume":0.0,"valor":0.0},"NFD":{"numero":"","serie":"","data":"","peso":0.0,"volume":0.0,"valor":0.0},"pedido":""}]}

REGRAS ESTRITAS DE EXTRAÇÃO E CONFERÊNCIA:
1. ENTIDADES (REMETENTE vs DESTINATÁRIO):
   - Se for DANFE: REMETENTE é o Emitente (topo esquerdo). DESTINATÁRIO fica no quadro "DESTINATÁRIO / REMETENTE".
   - Se for DACTE: Localize explicitamente os quadros "REMETENTE" e "DESTINATÁRIO". Preste atenção aos seus respectivos CNPJs e endereços. Não inverta os dados!
   - EXTRAÇÃO OBRIGATÓRIA DE CNPJ DO REMETENTE E DESTINATÁRIO:
     * Todo CNPJ possui obrigatoriamente 14 DÍGITOS NUMÉRICOS (ex: "06.626.253/0633-15" -> "06626253063315").
     * ATENÇÃO CRÍTICA: NUNCA extraia o número de telefone (ex: "FONE 8132555511") no lugar do CNPJ! Procure obrigatoriamente o campo "CNPJ" impresso ao lado ou abaixo do emitente/destinatário.
     * Tanto o Remetente quanto o Destinatário possuem CNPJ válido de 14 dígitos. Não deixe o CNPJ do Remetente em branco nem preencha com número de telefone!

2. DIVISÃO DAS NOTAS (NFO vs NFD):
   - ATENÇÃO: Identifique o tipo de documento e a NATUREZA DA OPERAÇÃO.
   - SE FOR DANFE DE VENDA/SAÍDA NORMAL: O número impresso no topo (cabeçalho) vai para o bloco **NFO** (Nota Fiscal Originária). Se houver notas referenciadas em Informações Complementares, vão para **NFD**.
   - SE FOR DANFE DE DEVOLUÇÃO / RETORNO (Natureza da operação contendo DEVOL, RETORNO, DEVOLUCAO, etc.):
     * A nota gerada no topo (cabeçalho do DANFE, ex: Nº 63691) é a Nota Fiscal de Devolução -> insira no bloco **NFD**. A "DATA DA EMISSÃO" do topo do DANFE vai para NFD.data (formato YYYY-MM-DD).
     * A NOTA FISCAL ORIGINAL QUE ESTÁ SENDO DEVOLVIDA fica localizada nos "DADOS ADICIONAIS / INFORMAÇÕES COMPLEMENTARES" ou no texto dos itens (ex: "NFO: 68148 EMISSÃO: 14/07/2026" ou "Nota: 68148 Data Emissao: 14/07/2026") -> insira no bloco **NFO** (numero: "68148", data: "2026-07-14")!
     * NUNCA coloque o número da NFD como NFO quando for devolução e houver uma nota de origem indicada nos Dados Adicionais!
   - SE FOR DACTE (Conhecimento de Transporte): O número no topo (cabeçalho) é o número do CT-e, NÃO é a NFO! A nota principal (NFO) em um DACTE deve ser encontrada nos quadros de "DOCUMENTOS ORIGINÁRIOS", "NOTAS FISCAIS" ou "INFORMAÇÕES DA NF-E". Insira os dados dessa nota no bloco **NFO** e, se houver devolução atrelada ao frete, no **NFD**.

3. VALOR TOTAL E PESO:
   - "valor": Valor total financeiro da operação (do documento).
   - "peso" e "volume": Extraia das informações de transporte/carga.

4. DADOS NUMÉRICOS E DATAS:
   - CNPJ e CEP contêm APENAS DÍGITOS NÚMEROS. Formate valores decimais com ponto (ex: 73.10).
   - ATENÇÃO A DATAS: No Brasil, as datas nos documentos estão no formato brasileiro DD/MM/YYYY (Dia/Mês/Ano). Exemplo: "07/08/2026" significa 7 de Agosto de 2026, devendo ser convertida para "2026-08-07". Não confunda o dia com o mês!

5. RAZÃO SOCIAL E CEP (PRECISÃO DE LEITURA):
   - RAZÃO SOCIAL / NOME DAS EMPRESAS: Preste atenção extrema aos caracteres exatos do nome comercial da empresa (ex: "MOKSHA8 BRASIL INDUSTRIA C M LTDA"). Não invente palavras genéricas nem altere números por letras (ex: não confunda "MOKSHA8" com "MORAES" ou "MORCELAMENTO").
   - CEP: O CEP possui obrigatoriamente 8 DÍGITOS NUMÉRICOS. Extraia com precisão os 8 dígitos do CEP constante no cabeçalho ou quadro de endereço (ex: "54355057", "88316003")."""
