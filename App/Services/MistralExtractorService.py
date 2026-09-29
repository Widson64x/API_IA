"""Implementação do extrator de DANFE utilizando o modelo Mistral AI (La Plateforme).

Utiliza a API compatível com OpenAI da Mistral para inferência rápida e barata usando modelos
como o pixtral-12b que tem 128k de contexto e visão nativa.
"""

import base64
import io
import json
import re

import httpx
from PIL import Image

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
            texto_pdf = self._extrair_texto_pdf(conteudo_arquivo)
            if len(texto_pdf.strip()) < 50:
                try:
                    print("[DEBUG MISTRAL] PDF escaneado; iniciando OCR documental...")
                    texto_pdf = await self._extrair_texto_ocr(conteudo_arquivo)
                except Exception as erro_ocr:
                    print(f"[DEBUG MISTRAL] OCR indisponível; mantendo visão: {erro_ocr}")
            
            lista_imagens = self._converter_pdf_para_imagens(conteudo_arquivo)
        else:
            lista_imagens = [self._otimizar_imagem_bytes(conteudo_arquivo)]

        prompt_enviado = prompt
        if texto_pdf.strip():
            prompt_enviado += f"\n\n--- TEXTO EXTRAÍDO DO DOCUMENTO PARA FACILITAR A LEITURA ---\n{texto_pdf}"

        # Prepara o payload para o modelo
        req_atual = [{"type": "text", "text": prompt_enviado}]
        
        for numero_pagina, imagem_bytes in enumerate(lista_imagens, start=1):
            req_atual.append({"type": "text", "text": f"PÁGINA {numero_pagina}:"})
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
            
            texto_resposta = resposta.choices[0].message.content or ""
            print(f"[DEBUG MISTRAL] Texto da resposta recebida (Tamanho: {len(texto_resposta)} caracteres):\n{texto_resposta[:300]}...")
            
            print(f"[DEBUG MISTRAL] Iniciando parse JSON da resposta...")
            dados_dict = self._limpar_e_converter_json(
                texto_resposta,
                conteudo_arquivo=conteudo_arquivo,
                nome_arquivo=nome_arquivo,
                texto_documento=texto_pdf,
            )

            if self._faltam_chaves(dados_dict):
                print("[DEBUG MISTRAL] Realizando conferência adicional das chaves de acesso...")
                alvos = self._listar_notas_sem_chave(dados_dict)
                prompt_chaves = f"""Leia EXCLUSIVAMENTE as chaves de acesso de NF-e das notas {alvos}.
Procure a chave da DANFE abaixo do código de barras e também a seção CHAVES NF-E/CT-E dos DACTEs anexos.
Cada chave de NF-e possui exatamente 44 dígitos, contém o modelo 55 nas posições 21 e 22 e traz o número da NF nas posições 26 a 34. Ignore chaves de CT-e, que contêm o modelo 57.
Confira visualmente os 44 dígitos duas vezes, mas escreva cada chave somente UMA VEZ no JSON. Não resuma, não trunque, não concatene, não complete e não retorne outros dados.
Responda somente neste formato JSON: {{"chaves":[{{"numero":"NUMERO_DA_NF","chave_acesso":"44_DIGITOS"}}]}}."""
                req_chaves = [{"type": "text", "text": prompt_chaves}]
                # A API Mistral aceita no máximo oito imagens por requisição.
                # A ordem preserva todas as faixas das primeiras páginas, que
                # normalmente concentram DANFE e DACTE com as chaves NF-e.
                imagens_conferencia = self._recortar_para_conferencia(
                    lista_imagens
                )[:8]
                for rotulo, imagem_bytes in imagens_conferencia:
                    req_chaves.append({"type": "text", "text": rotulo})
                    base64_imagem = base64.b64encode(imagem_bytes).decode("utf-8")
                    req_chaves.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_imagem}"
                            },
                        }
                    )
                try:
                    resposta_chaves = await cliente.chat.completions.create(
                        model=self.nome_modelo,
                        messages=[{"role": "user", "content": req_chaves}],
                        temperature=0,
                        timeout=60.0,
                    )
                    texto_chaves = resposta_chaves.choices[0].message.content or ""
                    print(
                        "[DEBUG MISTRAL] Resposta da conferência de chaves "
                        f"(Tamanho: {len(texto_chaves)} caracteres):\n"
                        f"{texto_chaves[:1200]}"
                    )
                    self._mesclar_chaves_do_texto(dados_dict, texto_chaves)
                except Exception as erro_conferencia:
                    print(
                        "[DEBUG MISTRAL] Conferência adicional indisponível; "
                        f"mantendo extração principal: {erro_conferencia}"
                    )

            await self._conferir_campos_criticos(
                cliente,
                dados_dict,
                lista_imagens,
            )
            print(f"[DEBUG MISTRAL] Parse concluído com sucesso!")
            
            return DadosDANFE(**dados_dict)

        except Exception as erro:
            erro_str = str(erro)
            print(f"[DEBUG MISTRAL] Falha/Timeout no modelo '{self.nome_modelo}' após {time.time() - t0:.2f}s: {erro_str}")
            raise ValueError(f"Falha ao extrair dados via Mistral AI. Erro: {erro_str}. Verifique se você inseriu uma chave válida em MISTRAL_API_KEY no arquivo .env ")

    async def _extrair_texto_ocr(self, conteudo_pdf: bytes) -> str:
        """Extrai a camada textual de PDFs escaneados pela API OCR da Mistral."""

        pdf_base64 = base64.b64encode(conteudo_pdf).decode("utf-8")
        payload = {
            "model": "mistral-ocr-latest",
            "document": {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{pdf_base64}",
            },
            "include_image_base64": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as cliente_http:
            resposta = await cliente_http.post(
                "https://api.mistral.ai/v1/ocr",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            resposta.raise_for_status()
        paginas = resposta.json().get("pages", [])
        return "\n\n".join(
            str(pagina.get("markdown", ""))
            for pagina in paginas
            if pagina.get("markdown")
        )

    async def _conferir_campos_criticos(
        self,
        cliente: AsyncOpenAI,
        dados: dict,
        imagens: list[bytes],
    ) -> None:
        """Confere endereço e peso apenas na DANFE principal, sem anexos."""

        if not imagens or not dados.get("notaFiscalList"):
            return

        alvos: list[dict] = []
        for item in dados["notaFiscalList"]:
            alvos.append(
                {
                    "Remetente": item.get("Remetente", {}),
                    "Destinatario": item.get("Destinatario", {}),
                    "NFD": {"numero": (item.get("NFD") or {}).get("numero")},
                }
            )

        imagem = Image.open(io.BytesIO(imagens[0])).convert("RGB")
        largura, altura = imagem.size
        regioes = (
            (
                "BLOCO ISOLADO DO REMETENTE/EMITENTE",
                (0, int(altura * 0.02), int(largura * 0.56), int(altura * 0.20)),
            ),
            (
                "BLOCO ISOLADO DO DESTINATARIO",
                (0, int(altura * 0.17), largura, int(altura * 0.32)),
            ),
            (
                "TRANSPORTADOR E PESO BRUTO",
                (0, int(altura * 0.31), largura, int(altura * 0.49)),
            ),
        )

        prompt = f"""Confira somente a DANFE atual mostrada nesta imagem. Ignore completamente DACTE, CT-e e anexos.
Entidades e número esperado: {json.dumps(alvos, ensure_ascii=False)}.
Leia literalmente as linhas de endereço do Remetente e do Destinatario. Quando houver "LOGRADOURO, NUMERO - BAIRRO", separe endereco, numero e bairro. O trecho textual depois do hífen pertence obrigatoriamente ao bairro, mesmo que não exista uma coluna chamada BAIRRO. Preserve S/N somente como numero; não use S/N como bairro se houver um nome depois do hífen.
Para a NFD, leia peso exclusivamente da célula PESO BRUTO do quadro TRANSPORTADOR / VOLUMES TRANSPORTADOS desta DANFE. Não use peso, cubagem ou peso de cálculo de DACTE.
Responda somente JSON neste formato: {{"notaFiscalList":[{{"Remetente":{{"cnpj":null,"endereco":null,"bairro":null,"numero":null}},"Destinatario":{{"cnpj":null,"endereco":null,"bairro":null,"numero":null}},"NFD":{{"numero":null,"peso":null}}}}]}}."""
        conteudo = [{"type": "text", "text": prompt}]
        for rotulo, caixa in regioes:
            recorte = imagem.crop(caixa)
            if recorte.width < 3400:
                proporcao = 3400 / recorte.width
                recorte = recorte.resize(
                    (3400, int(recorte.height * proporcao)),
                    Image.Resampling.LANCZOS,
                )
            buffer = io.BytesIO()
            recorte.save(buffer, format="JPEG", quality=96, optimize=True)
            imagem_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            conteudo.extend(
                [
                    {"type": "text", "text": rotulo},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{imagem_b64}"
                        },
                    },
                ]
            )

        try:
            resposta = await cliente.chat.completions.create(
                model=self.nome_modelo,
                messages=[{"role": "user", "content": conteudo}],
                temperature=0,
                timeout=60.0,
            )
            texto = resposta.choices[0].message.content or ""
            print(
                "[DEBUG MISTRAL] Resposta da conferência de campos críticos "
                f"(Tamanho: {len(texto)} caracteres):\n{texto[:1200]}"
            )
            correspondencia = re.search(
                r"```(?:json)?\s*(\{.*\})\s*```",
                texto.strip(),
                re.DOTALL,
            )
            objeto = json.loads(
                correspondencia.group(1) if correspondencia else texto.strip()
            )
            if isinstance(objeto, dict):
                self._mesclar_campos_criticos(dados, objeto)
        except Exception as erro:
            print(
                "[DEBUG MISTRAL] Conferência de campos críticos indisponível; "
                f"mantendo dados validados: {erro}"
            )

    def _mesclar_campos_criticos(self, destino: dict, origem: dict) -> None:
        """Mescla somente endereço e peso associados à mesma entidade/nota."""

        itens_origem = origem.get("notaFiscalList", [])
        for indice, item in enumerate(destino.get("notaFiscalList", [])):
            if indice >= len(itens_origem) or not isinstance(itens_origem[indice], dict):
                continue
            confirmado = itens_origem[indice]

            for entidade_nome in ("Remetente", "Destinatario"):
                entidade = item.get(entidade_nome)
                entidade_confirmada = confirmado.get(entidade_nome)
                if not isinstance(entidade, dict) or not isinstance(
                    entidade_confirmada, dict
                ):
                    continue
                cnpj_atual = re.sub(r"\D", "", str(entidade.get("cnpj", "")))
                cnpj_confirmado = re.sub(
                    r"\D", "", str(entidade_confirmada.get("cnpj", ""))
                )
                if (
                    cnpj_atual
                    and cnpj_confirmado
                    and cnpj_atual != cnpj_confirmado
                    and cnpj_atual[:8] != cnpj_confirmado[:8]
                ):
                    continue
                entidade_confirmada = entidade_confirmada.copy()
                self._normalizar_entidade(entidade_confirmada, "")
                for campo in ("endereco", "bairro", "numero"):
                    valor = entidade_confirmada.get(campo)
                    if valor and valor != "S/N":
                        entidade[campo] = valor

            nfd = item.get("NFD")
            nfd_confirmada = confirmado.get("NFD")
            if not isinstance(nfd, dict) or not isinstance(nfd_confirmada, dict):
                continue
            numero_atual = str(nfd.get("numero", "")).lstrip("0") or "0"
            numero_confirmado = (
                str(nfd_confirmada.get("numero", "")).lstrip("0") or "0"
            )
            peso = self._converter_decimal(nfd_confirmada.get("peso"))
            if numero_atual == numero_confirmado and peso is not None and peso > 0:
                nfd["peso"] = peso

    @staticmethod
    def _faltam_chaves(dados: dict) -> bool:
        """Indica se uma nota identificada ainda não possui sua chave validada."""

        return bool(ExtratorMistral._listar_notas_sem_chave(dados))

    @staticmethod
    def _listar_notas_sem_chave(dados: dict) -> list[dict[str, str]]:
        """Lista números que justificam uma segunda leitura visual."""

        faltantes: list[dict[str, str]] = []
        for item in dados.get("notaFiscalList", []):
            for tipo in ("NFO", "NFD"):
                nota = item.get(tipo)
                if (
                    isinstance(nota, dict)
                    and nota.get("numero")
                    and not nota.get("chave_acesso")
                ):
                    faltantes.append({"tipo": tipo, "numero": str(nota["numero"])})
        return faltantes

    @staticmethod
    def _recortar_para_conferencia(
        imagens: list[bytes],
    ) -> list[tuple[str, bytes]]:
        """Divide páginas em faixas ampliadas para leitura dos 44 dígitos."""

        recortes: list[tuple[str, bytes]] = []
        for numero_pagina, imagem_bytes in enumerate(imagens, start=1):
            imagem = Image.open(io.BytesIO(imagem_bytes)).convert("RGB")
            largura, altura = imagem.size
            regioes = (
                ("FAIXA SUPERIOR", (0, 0, largura, int(altura * 0.38))),
                (
                    "FAIXA CENTRAL",
                    (0, int(altura * 0.28), largura, int(altura * 0.72)),
                ),
                ("FAIXA INFERIOR", (0, int(altura * 0.62), largura, altura)),
                (
                    "QUADRO CHAVES NF-E/CT-E",
                    (
                        int(largura * 0.35),
                        int(altura * 0.52),
                        largura,
                        int(altura * 0.90),
                    ),
                ),
            )
            for nome_regiao, caixa in regioes:
                recorte = imagem.crop(caixa)
                if recorte.width < 2400:
                    proporcao = 2400 / recorte.width
                    recorte = recorte.resize(
                        (2400, int(recorte.height * proporcao)),
                        Image.Resampling.LANCZOS,
                    )
                buffer = io.BytesIO()
                recorte.save(
                    buffer,
                    format="JPEG",
                    quality=95,
                    optimize=True,
                )
                recortes.append(
                    (f"PÁGINA {numero_pagina} — {nome_regiao}:", buffer.getvalue())
                )
        return recortes

    @classmethod
    def _mesclar_chaves_do_texto(cls, destino: dict, texto: str) -> None:
        """Associa somente chaves NF-e válidas ao número contido na própria chave."""

        chaves_validas = cls._extrair_chaves_acesso(texto)
        # Alguns modelos podem repetir uma chave sem separador. Se a sequência
        # possuir blocos exatos de 44 dígitos, cada bloco ainda precisa passar
        # integralmente pelo dígito verificador antes de ser aceito.
        for sequencia in re.findall(r"(?<!\d)\d{88,}(?!\d)", texto):
            if len(sequencia) % 44:
                continue
            for inicio in range(0, len(sequencia), 44):
                candidata = sequencia[inicio : inicio + 44]
                if cls._chave_acesso_valida(candidata) and candidata not in chaves_validas:
                    chaves_validas.append(candidata)

        chaves_por_numero = {
            chave[25:34].lstrip("0") or "0": chave
            for chave in chaves_validas
        }
        for item in destino.get("notaFiscalList", []):
            for tipo in ("NFO", "NFD"):
                nota = item.get(tipo)
                if not isinstance(nota, dict) or not nota.get("numero"):
                    continue
                numero = str(nota["numero"]).lstrip("0") or "0"
                chave = chaves_por_numero.get(numero)
                if chave:
                    nota["chave_acesso"] = chave
                    nota["serie"] = chave[22:25].lstrip("0") or "0"

    @staticmethod
    def _mesclar_conferencia(destino: dict, origem: dict) -> None:
        """Mescla campos da conferência quando associados ao mesmo número de NF."""

        notas_por_numero: dict[str, dict] = {}
        for item in origem.get("notaFiscalList", []):
            for tipo in ("NFO", "NFD"):
                nota = item.get(tipo)
                if isinstance(nota, dict) and nota.get("numero"):
                    notas_por_numero[str(nota["numero"])] = nota

        itens_origem = origem.get("notaFiscalList", [])
        for indice, item in enumerate(destino.get("notaFiscalList", [])):
            if indice < len(itens_origem):
                item_origem = itens_origem[indice]
                for entidade_nome in ("Remetente", "Destinatario"):
                    entidade = item.get(entidade_nome)
                    confirmada = item_origem.get(entidade_nome)
                    if not isinstance(entidade, dict) or not isinstance(confirmada, dict):
                        continue
                    if (
                        confirmada.get("cnpj") == entidade.get("cnpj")
                        and confirmada.get("nome")
                    ):
                        entidade["nome"] = confirmada["nome"]

            for tipo in ("NFO", "NFD"):
                nota = item.get(tipo)
                if not isinstance(nota, dict):
                    continue
                confirmada = notas_por_numero.get(str(nota.get("numero", "")))
                if not confirmada:
                    continue
                for campo in ("chave_acesso", "data"):
                    if confirmada.get(campo):
                        nota[campo] = confirmada[campo]
                if tipo == "NFD":
                    for campo in ("peso", "volume", "valor"):
                        nota.pop(campo, None)
                        if confirmada.get(campo) is not None:
                            nota[campo] = confirmada[campo]
