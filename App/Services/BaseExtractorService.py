"""Contrato e utilitários compartilhados pelos extratores de DANFE."""

import io
import json
import re
import unicodedata
from abc import ABC, abstractmethod
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, List, Optional

import pymupdf
from PIL import Image

from App.Schemas.DanfeSchema import DadosDANFE


class DANFEExtratorBase(ABC):
    """Contrato comum dos provedores e validação defensiva da resposta da IA."""

    _VALORES_AUSENTES = {
        "",
        "-",
        "n/a",
        "na",
        "null",
        "none",
        "não consta",
        "nao consta",
        "não encontrado",
        "nao encontrado",
        "não informado",
        "nao informado",
    }

    @abstractmethod
    async def extrair_dados(
        self,
        conteudo_arquivo: bytes,
        nome_arquivo: str,
    ) -> DadosDANFE:
        """Extrai e valida os dados fiscais do arquivo recebido."""

    def _converter_pdf_para_imagens(
        self,
        conteudo_pdf: bytes,
        dpi: int = 200,
    ) -> List[bytes]:
        """Renderiza cada página do PDF em uma imagem JPEG independente.

        Manter as páginas separadas evita a perda de legibilidade causada por uma
        imagem vertical muito alta e permite ao modelo distinguir DANFE de anexos.
        """

        imagens: List[bytes] = []
        documento = pymupdf.open(stream=conteudo_pdf, filetype="pdf")
        try:
            zoom = dpi / 72
            matriz = pymupdf.Matrix(zoom, zoom)
            for pagina in documento:
                pixmap = pagina.get_pixmap(matrix=matriz, alpha=False)
                imagem = Image.open(io.BytesIO(pixmap.tobytes("jpeg"))).convert("RGB")
                buffer = io.BytesIO()
                imagem.save(buffer, format="JPEG", quality=88, optimize=True)
                imagens.append(buffer.getvalue())
        finally:
            documento.close()
        return imagens

    def _extrair_texto_pdf(self, conteudo_pdf: bytes) -> str:
        """Obtém a camada textual do PDF, quando existente."""

        try:
            documento = pymupdf.open(stream=conteudo_pdf, filetype="pdf")
            try:
                return "\n".join(pagina.get_text() for pagina in documento)
            finally:
                documento.close()
        except Exception:
            return ""

    def _limpar_e_converter_json(
        self,
        texto_resposta: str,
        *,
        conteudo_arquivo: Optional[bytes] = None,
        nome_arquivo: Optional[str] = None,
        texto_documento: Optional[str] = None,
    ) -> dict[str, Any]:
        """Converte a resposta JSON e a reconcilia com o documento de origem."""

        texto_limpo = texto_resposta.strip()
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texto_limpo, re.DOTALL)
        if match:
            texto_limpo = match.group(1).strip()

        try:
            parsed = json.loads(texto_limpo)
        except json.JSONDecodeError as erro:
            raise ValueError(
                "Falha ao decodificar o JSON retornado pelo modelo: "
                f"{erro.msg} (linha {erro.lineno}, coluna {erro.colno})."
            ) from erro

        if not isinstance(parsed, dict):
            raise ValueError("O modelo deve retornar um único objeto JSON.")

        texto_origem = texto_documento or ""
        if not texto_origem and conteudo_arquivo and nome_arquivo:
            if Path(nome_arquivo).suffix.lower() == ".pdf":
                texto_origem = self._extrair_texto_pdf(conteudo_arquivo)

        return self._validar_e_corrigir_extracao(
            parsed,
            texto_documento=texto_origem,
            conteudo_arquivo=conteudo_arquivo,
            nome_arquivo=nome_arquivo,
        )

    def _validar_e_corrigir_extracao(
        self,
        dados: dict[str, Any],
        *,
        texto_documento: str = "",
        conteudo_arquivo: Optional[bytes] = None,
        nome_arquivo: Optional[str] = None,
    ) -> dict[str, Any]:
        """Normaliza campos e descarta identificadores sem evidência confiável."""

        dados = self._normalizar_ausentes(dados)
        notas_brutas = dados.get("notaFiscalList")
        notas = notas_brutas if isinstance(notas_brutas, list) else []
        notas_validas: list[dict[str, Any]] = []
        digitos_documento = re.sub(r"\D", "", texto_documento)
        chaves_documento = self._extrair_chaves_acesso(texto_documento)
        cnpjs_papeis = (
            self._extrair_cnpjs_papeis(texto_documento) if len(notas) == 1 else {}
        )

        for nota_bruta in notas:
            if not isinstance(nota_bruta, dict):
                continue
            nota = nota_bruta.copy()
            for entidade_nome in ("Remetente", "Destinatario"):
                entidade = nota.get(entidade_nome)
                if not isinstance(entidade, dict):
                    nota.pop(entidade_nome, None)
                    continue
                self._normalizar_entidade(entidade, digitos_documento)
                self._reconciliar_nome_com_ocr(entidade, texto_documento)
                if not entidade:
                    nota.pop(entidade_nome, None)

            for entidade_nome, papel in (
                ("Remetente", "emitente"),
                ("Destinatario", "destinatario"),
            ):
                cnpj_confirmado = cnpjs_papeis.get(papel)
                if cnpj_confirmado:
                    entidade = nota.setdefault(entidade_nome, {})
                    entidade["cnpj"] = cnpj_confirmado

            remetente = nota.get("Remetente")
            destinatario = nota.get("Destinatario")
            if (
                isinstance(remetente, dict)
                and isinstance(destinatario, dict)
                and remetente.get("cnpj")
                and remetente.get("cnpj") == destinatario.get("cnpj")
            ):
                destinatario.pop("cnpj", None)
                if self._texto_comparavel(remetente.get("nome")) == self._texto_comparavel(
                    destinatario.get("nome")
                ):
                    nota.pop("Destinatario", None)

            for bloco_nome in ("NFO", "NFD"):
                bloco = nota.get(bloco_nome)
                if not isinstance(bloco, dict):
                    nota.pop(bloco_nome, None)
                    continue
                self._normalizar_nota(bloco, digitos_documento)
                self._associar_chave_por_numero(bloco, chaves_documento)
                if not bloco:
                    nota.pop(bloco_nome, None)

            nfd = nota.get("NFD")
            if isinstance(nfd, dict):
                self._reconciliar_peso_bruto(nfd, texto_documento)

            self._corrigir_semantica_nfo_nfd(
                nota,
                texto_documento,
                usar_primeira_chave=len(notas) == 1,
            )

            if texto_documento and "pedido" not in texto_documento.casefold():
                nota.pop("pedido", None)

            nota = self._normalizar_ausentes(nota)
            if nota and not self._nota_duplicada(nota, notas_validas):
                notas_validas.append(nota)

        resultado: dict[str, Any] = {
            "quantidade_nota": len(notas_validas),
            "notaFiscalList": notas_validas,
        }
        if nome_arquivo:
            caminho = Path(nome_arquivo)
            resultado["arquivo"] = caminho.stem
            resultado["extensao"] = caminho.suffix.lower().lstrip(".")
        if conteudo_arquivo is not None:
            resultado["tamanho"] = str(len(conteudo_arquivo))

        # A data de criação só é aceita se realmente veio do documento. O nome,
        # extensão e tamanho são sempre derivados do upload, nunca da IA.
        data_criacao = dados.get("data_criacao")
        if data_criacao and texto_documento and str(data_criacao) in texto_documento:
            resultado["data_criacao"] = data_criacao
        return resultado

    def _normalizar_entidade(
        self,
        entidade: dict[str, Any],
        digitos_documento: str,
    ) -> None:
        """Normaliza e valida os identificadores de uma empresa."""

        cnpj = re.sub(r"\D", "", str(entidade.get("cnpj", "")))
        if not self._cnpj_valido(cnpj) or (
            digitos_documento and cnpj not in digitos_documento
        ):
            entidade.pop("cnpj", None)
        else:
            entidade["cnpj"] = cnpj

        cep = re.sub(r"\D", "", str(entidade.get("cep", "")))
        if len(cep) != 8 or (digitos_documento and cep not in digitos_documento):
            entidade.pop("cep", None)
        else:
            entidade["cep"] = cep

        uf = str(entidade.get("uf", "")).strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", uf):
            entidade.pop("uf", None)
        else:
            entidade["uf"] = uf

        endereco = entidade.get("endereco")
        if isinstance(endereco, str):
            # Confusão recorrente do OCR em rodovias; "RGD BR" não é um
            # prefixo de logradouro válido, enquanto "ROD BR" é impresso.
            entidade["endereco"] = re.sub(
                r"^RGD\s+BR\b",
                "ROD BR",
                endereco,
                flags=re.IGNORECASE,
            )

    @classmethod
    def _reconciliar_nome_com_ocr(
        cls,
        entidade: dict[str, Any],
        texto_documento: str,
    ) -> None:
        """Prefere uma repetição limpa do nome encontrada no próprio OCR."""

        nome = entidade.get("nome")
        if not nome or not texto_documento:
            return
        nome_base = cls._texto_comparavel(nome)
        melhor_nome: Optional[str] = None
        melhor_similaridade = 0.0
        for linha in texto_documento.splitlines():
            candidata = linha.strip(" \t#*-_")
            if not candidata or "|" in candidata:
                continue
            candidata_base = cls._texto_comparavel(candidata)
            if not candidata_base:
                continue
            proporcao = len(candidata_base) / max(len(nome_base), 1)
            if not 0.75 <= proporcao <= 1.25:
                continue
            similaridade = SequenceMatcher(None, nome_base, candidata_base).ratio()
            if similaridade >= 0.88 and similaridade > melhor_similaridade:
                melhor_nome = candidata
                melhor_similaridade = similaridade
        if melhor_nome:
            entidade["nome"] = melhor_nome

    def _normalizar_nota(
        self,
        bloco: dict[str, Any],
        digitos_documento: str,
    ) -> None:
        """Normaliza uma nota e usa a chave para conferir número e série."""

        chave = re.sub(r"\D", "", str(bloco.get("chave_acesso", "")))
        chave_confiavel = self._chave_acesso_valida(chave) and (
            not digitos_documento or chave in digitos_documento
        )
        if chave_confiavel:
            bloco["chave_acesso"] = chave
            bloco["serie"] = chave[22:25].lstrip("0") or "0"
            bloco["numero"] = chave[25:34].lstrip("0") or "0"
        else:
            bloco.pop("chave_acesso", None)
            numero = re.sub(r"\D", "", str(bloco.get("numero", "")))
            if not numero or len(numero) > 9:
                bloco.pop("numero", None)
            else:
                bloco["numero"] = numero.lstrip("0") or "0"
            serie = re.sub(r"\D", "", str(bloco.get("serie", "")))
            if not serie or len(serie) > 3:
                bloco.pop("serie", None)
            else:
                bloco["serie"] = serie.lstrip("0") or "0"

        data = self._normalizar_data(bloco.get("data"))
        if data:
            bloco["data"] = data
        else:
            bloco.pop("data", None)

        for campo in ("peso", "volume", "valor"):
            valor = self._converter_decimal(bloco.get(campo))
            if valor is None or valor == 0:
                bloco.pop(campo, None)
            else:
                bloco[campo] = valor

    @staticmethod
    def _associar_chave_por_numero(
        bloco: dict[str, Any],
        chaves_documento: list[str],
    ) -> None:
        """Preenche chave comprovada no OCR quando o número já foi identificado."""

        if bloco.get("chave_acesso") or not bloco.get("numero"):
            return
        numero_bloco = str(bloco["numero"])
        for chave in chaves_documento:
            numero_chave = chave[25:34].lstrip("0") or "0"
            if numero_chave == numero_bloco:
                bloco["chave_acesso"] = chave
                bloco["serie"] = chave[22:25].lstrip("0") or "0"
                return

    def _reconciliar_peso_bruto(
        self,
        bloco: dict[str, Any],
        texto_documento: str,
    ) -> None:
        """Confirma o peso exclusivamente pelo campo PESO BRUTO da DANFE."""

        if not texto_documento or not re.search(
            r"PESO\s+BRUTO",
            texto_documento,
            re.IGNORECASE,
        ):
            return
        correspondencia = re.search(
            r"PESO\s+BRUTO\s*(?:\|\s*)?(\d{1,6}(?:[.,]\d{1,4})?)",
            texto_documento,
            re.IGNORECASE,
        )
        if not correspondencia:
            bloco.pop("peso", None)
            return
        peso = self._converter_decimal(correspondencia.group(1))
        if peso is None or peso == 0:
            bloco.pop("peso", None)
        else:
            bloco["peso"] = peso

    def _corrigir_semantica_nfo_nfd(
        self,
        nota: dict[str, Any],
        texto_documento: str,
        *,
        usar_primeira_chave: bool,
    ) -> None:
        """Garante NFO=original e NFD=devolução quando a natureza é explícita."""

        if not texto_documento:
            return
        texto = texto_documento.casefold()
        eh_devolucao = any(
            termo in texto
            for termo in ("devolucao", "devolução", "estorno", "retorno")
        )
        if not eh_devolucao:
            return

        chaves = self._extrair_chaves_acesso(texto_documento)
        if not chaves:
            return
        chave_principal = (
            chaves[0]
            if usar_primeira_chave
            else self._localizar_chave_principal(nota, chaves)
        )
        if not chave_principal:
            return
        numero_principal = chave_principal[25:34].lstrip("0") or "0"
        nfo = nota.get("NFO") if isinstance(nota.get("NFO"), dict) else None
        nfd = nota.get("NFD") if isinstance(nota.get("NFD"), dict) else None

        if nfo and nfo.get("numero") == numero_principal:
            nota["NFO"], nota["NFD"] = nfd, nfo
            nfd = nota.get("NFD")
            nfo = nota.get("NFO")

        if not nfd:
            nfd = {}
            nota["NFD"] = nfd
        nfd["chave_acesso"] = chave_principal
        nfd["numero"] = numero_principal
        nfd["serie"] = chave_principal[22:25].lstrip("0") or "0"

        if nfo and not nfo.get("chave_acesso") and nfo.get("numero"):
            for chave in chaves[1:]:
                numero = chave[25:34].lstrip("0") or "0"
                if numero == nfo["numero"]:
                    nfo["chave_acesso"] = chave
                    nfo["serie"] = chave[22:25].lstrip("0") or "0"
                    break

        # A DANFE de devolução não comprova peso, volumes ou valor da nota
        # original apenas por repetir os produtos devolvidos.
        if nfo:
            for campo in ("peso", "volume", "valor"):
                nfo.pop(campo, None)

    @staticmethod
    def _localizar_chave_principal(
        nota: dict[str, Any],
        chaves: list[str],
    ) -> Optional[str]:
        """Associa uma das chaves do documento ao item devolvido pelo modelo."""

        for bloco_nome in ("NFD", "NFO"):
            bloco = nota.get(bloco_nome)
            if not isinstance(bloco, dict):
                continue
            chave = bloco.get("chave_acesso")
            if chave in chaves:
                return str(chave)
            numero = bloco.get("numero")
            if numero:
                for candidata in chaves:
                    numero_chave = candidata[25:34].lstrip("0") or "0"
                    if numero_chave == numero:
                        return candidata
        return None

    @staticmethod
    def _nota_duplicada(
        nota: dict[str, Any],
        existentes: list[dict[str, Any]],
    ) -> bool:
        """Evita que anexos façam a IA repetir a mesma DANFE na lista."""

        def identidade(item: dict[str, Any]) -> tuple[Any, ...]:
            for bloco_nome in ("NFD", "NFO"):
                bloco = item.get(bloco_nome)
                if isinstance(bloco, dict) and bloco.get("chave_acesso"):
                    return ("chave", bloco["chave_acesso"])
            remetente = item.get("Remetente") or {}
            for bloco_nome in ("NFD", "NFO"):
                bloco = item.get(bloco_nome)
                if isinstance(bloco, dict) and bloco.get("numero"):
                    return (
                        "numero",
                        bloco.get("numero"),
                        bloco.get("serie"),
                        remetente.get("cnpj"),
                    )
            return ("objeto", json.dumps(item, sort_keys=True, ensure_ascii=False))

        chave = identidade(nota)
        return any(identidade(existente) == chave for existente in existentes)

    @staticmethod
    def _texto_comparavel(valor: Any) -> str:
        """Reduz texto para comparação tolerante a acentos e pontuação."""

        texto = unicodedata.normalize("NFKD", str(valor or ""))
        texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
        return re.sub(r"\W", "", texto).casefold()

    @classmethod
    def _extrair_cnpjs_papeis(cls, texto: str) -> dict[str, str]:
        """Obtém CNPJs dos quadros de emitente e destinatário em PDFs textuais."""

        texto_busca = unicodedata.normalize("NFKD", texto)
        texto_busca = "".join(
            caractere
            for caractere in texto_busca
            if not unicodedata.combining(caractere)
        ).upper()
        inicio_emitente = texto_busca.find("IDENTIFICACAO DO EMITENTE")
        inicio_destinatario = texto_busca.find(
            "DESTINATARIO / REMETENTE",
            max(inicio_emitente, 0),
        )
        inicio_calculo = texto_busca.find(
            "CALCULO DO IMPOSTO",
            max(inicio_destinatario, 0),
        )
        if inicio_emitente < 0 or inicio_destinatario < 0:
            return {}

        padrao = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")

        def cnpjs_no_trecho(inicio: int, fim: int) -> list[str]:
            encontrados: list[str] = []
            for valor in padrao.findall(texto[inicio:fim]):
                cnpj = re.sub(r"\D", "", valor)
                if cls._cnpj_valido(cnpj):
                    encontrados.append(cnpj)
            return encontrados

        emitentes = cnpjs_no_trecho(inicio_emitente, inicio_destinatario)
        fim_destinatario = inicio_calculo if inicio_calculo > inicio_destinatario else len(texto)
        destinatarios = cnpjs_no_trecho(inicio_destinatario, fim_destinatario)
        resultado: dict[str, str] = {}
        if emitentes:
            resultado["emitente"] = emitentes[-1]
        if destinatarios:
            resultado["destinatario"] = destinatarios[0]
        return resultado

    @classmethod
    def _normalizar_ausentes(cls, valor: Any) -> Any:
        """Remove campos vazios recursivamente sem inventar valores padrão."""

        if isinstance(valor, dict):
            return {
                chave: normalizado
                for chave, item in valor.items()
                if (normalizado := cls._normalizar_ausentes(item)) is not None
            }
        if isinstance(valor, list):
            return [
                normalizado
                for item in valor
                if (normalizado := cls._normalizar_ausentes(item)) is not None
            ]
        if isinstance(valor, str):
            limpo = valor.strip()
            if limpo.casefold() in cls._VALORES_AUSENTES:
                return None
            return limpo
        return valor

    @staticmethod
    def _converter_decimal(valor: Any) -> Optional[float]:
        """Converte números brasileiros ou internacionais em ``float``."""

        if valor is None or isinstance(valor, bool):
            return None
        if isinstance(valor, (int, float)):
            return float(valor)
        texto = re.sub(r"[^\d,.-]", "", str(valor))
        if not texto:
            return None
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        try:
            return float(texto)
        except ValueError:
            return None

    @staticmethod
    def _normalizar_data(valor: Any) -> Optional[str]:
        """Normaliza datas completas; mês/ano isolado é mantido como evidência parcial."""

        if valor is None:
            return None
        texto = str(valor).strip()
        for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(texto, formato).date().isoformat()
            except ValueError:
                pass
        if re.fullmatch(r"(?:0[1-9]|1[0-2])/\d{4}", texto):
            return texto
        return None

    @staticmethod
    def _cnpj_valido(cnpj: str) -> bool:
        """Valida os dois dígitos verificadores do CNPJ."""

        if len(cnpj) != 14 or len(set(cnpj)) == 1:
            return False

        def calcular(base: str, pesos: list[int]) -> str:
            soma = sum(int(digito) * peso for digito, peso in zip(base, pesos))
            resto = soma % 11
            return "0" if resto < 2 else str(11 - resto)

        primeiro = calcular(cnpj[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        segundo = calcular(
            cnpj[:12] + primeiro,
            [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
        )
        return cnpj[-2:] == primeiro + segundo

    @staticmethod
    def _chave_acesso_valida(chave: str) -> bool:
        """Valida tamanho e dígito verificador de uma chave de NF-e."""

        if len(chave) != 44 or not chave.isdigit() or chave[20:22] != "55":
            return False
        corpo = chave[:43]
        soma = 0
        peso = 2
        for digito in reversed(corpo):
            soma += int(digito) * peso
            peso = 2 if peso == 9 else peso + 1
        resto = soma % 11
        verificador = 0 if resto in (0, 1) else 11 - resto
        return int(chave[-1]) == verificador

    @classmethod
    def _extrair_chaves_acesso(cls, texto: str) -> list[str]:
        """Localiza chaves válidas mesmo quando estão agrupadas com espaços."""

        chaves: list[str] = []
        for candidato in re.findall(r"(?<!\d)(?:\d[ .-]?){44}(?!\d)", texto):
            chave = re.sub(r"\D", "", candidato)
            if cls._chave_acesso_valida(chave) and chave not in chaves:
                chaves.append(chave)
        return chaves

    def _otimizar_imagem_bytes(
        self,
        conteudo_imagem: bytes,
        max_dimensao: int = 1600,
    ) -> bytes:
        """Redimensiona uma imagem preservando proporção e legibilidade."""

        try:
            imagem = Image.open(io.BytesIO(conteudo_imagem)).convert("RGB")
            largura, altura = imagem.size
            if max(largura, altura) > max_dimensao:
                proporcao = max_dimensao / float(max(largura, altura))
                imagem = imagem.resize(
                    (int(largura * proporcao), int(altura * proporcao)),
                    Image.Resampling.LANCZOS,
                )
            buffer = io.BytesIO()
            imagem.save(buffer, format="JPEG", quality=85, optimize=True)
            return buffer.getvalue()
        except Exception:
            return conteudo_imagem

    def _obter_prompt_instrucao(self) -> str:
        """Retorna regras de extração sem exemplos que contaminem a resposta."""

        return """Analise todas as páginas deste arquivo e extraia somente DANFEs de NF-e.
Ignore completamente DACTE/CT-e, comprovantes, canhotos isolados, etiquetas, fotos de caixas e outros anexos. Cada DANFE gera exatamente um item em notaFiscalList.

Retorne somente um objeto JSON válido, sem Markdown, comentários ou explicações, com esta estrutura. OMITE qualquer campo cujo valor não esteja legível ou comprovado no documento:
{"notaFiscalList":[{"Remetente":{"nome":null,"cnpj":null,"cep":null,"endereco":null,"cidade":null,"uf":null,"bairro":null,"numero":null},"Destinatario":{"nome":null,"cnpj":null,"cep":null,"endereco":null,"cidade":null,"uf":null,"bairro":null,"numero":null},"NFO":{"numero":null,"serie":null,"data":null,"chave_acesso":null,"peso":null,"volume":null,"valor":null},"NFD":{"numero":null,"serie":null,"data":null,"chave_acesso":null,"peso":null,"volume":null,"valor":null},"pedido":null}]}

REGRAS OBRIGATÓRIAS:
1. Não invente, complete, estime, copie de exemplos ou repita dados para preencher campos. Não use string vazia, N/A ou zero para dado ausente: omita o campo.
2. Remetente é exclusivamente o EMITENTE no cabeçalho da DANFE. Destinatario é exclusivamente a empresa no quadro DESTINATÁRIO / REMETENTE. Transportadora, expedidor, recebedor e tomador nunca são Remetente ou Destinatario. cidade vem do campo MUNICÍPIO; bairro vem do campo BAIRRO / DISTRITO — não os inverta.
3. NFD significa Nota Fiscal de Devolução: quando a natureza indicar devolução, retorno ou estorno, coloque em NFD o número, série, data, chave, peso, volumes e valor total da DANFE atual.
4. NFO significa Nota Fiscal Original: coloque em NFO apenas a nota original referenciada pela devolução, priorizando uma indicação explícita como "NFO", "NF Origem" ou equivalente. Não copie peso, volume ou valor da NFD para a NFO. Não confunda pedido, lote, protocolo, inscrição estadual, CT-e ou outra NF-e referenciada por motivo diferente com a NFO.
5. Em uma nota comum que não seja devolução/retorno/estorno, coloque a DANFE atual em NFO e omita NFD.
6. chave_acesso possui exatamente 44 dígitos. Remova espaços e pontuação, mas nunca complete dígitos. Confira todos os 44 dígitos uma segunda vez antes de responder. Inclua a chave separadamente em NFO e NFD somente quando estiver associada à respectiva nota.
7. Use VALOR TOTAL DA NOTA, não total dos produtos. Peso é exclusivamente o campo PESO BRUTO da própria DANFE; se a célula estiver vazia, omita peso. Volume é QUANTIDADE no quadro TRANSPORTADOR / VOLUMES TRANSPORTADOS. Nunca use peso, cubagem, quantidade ou valor de DACTE/CT-e, etiqueta ou foto.
8. pedido só pode conter um número explicitamente rotulado como pedido. Motivo de devolução não é pedido.
9. CNPJ contém 14 dígitos, CEP contém 8 dígitos, série contém no máximo 3 dígitos e número da NF contém no máximo 9 dígitos.
10. Não transforme mês/ano em uma data completa: se só estiver legível 03/2026, retorne exatamente 03/2026 e não invente um dia.
11. quantidade_nota não é necessária; o servidor a calcula pela lista."""
