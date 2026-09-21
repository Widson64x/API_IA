"""Implementação do extrator de DANFE utilizando o modelo Mistral AI (La Plateforme).

Utiliza a API compatível com OpenAI da Mistral para inferência rápida e barata usando modelos
como o pixtral-12b que tem 128k de contexto e visão nativa.
"""

import base64
import io

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
                prompt_chaves = f"""Faça uma conferência visual final das DANFEs para estas notas: {alvos}.
Responda em JSON neste formato: {{"notaFiscalList":[{{"Remetente":{{"nome":null,"cnpj":null}},"Destinatario":{{"nome":null,"cnpj":null}},"NFO":{{"numero":null,"data":null,"chave_acesso":null}},"NFD":{{"numero":null,"data":null,"chave_acesso":null,"peso":null,"volume":null,"valor":null}}}}]}}.
Cada chave de NF-e tem exatamente 44 dígitos e contém o modelo 55 nas posições 21 e 22. Não retorne chave de CT-e, cujo modelo é 57. Não invente nem complete dígitos ilegíveis.
Copie os nomes exatamente como estão impressos. Para NFD, peso só pode vir da célula PESO BRUTO da DANFE; se estiver vazia, omita. Nunca use peso/cubagem do DACTE.
Você pode usar a seção CHAVES NF-E de um DACTE somente para completar uma NFO já identificada pelo mesmo número; não transforme o DACTE em outra nota."""
                req_chaves = [{"type": "text", "text": prompt_chaves}]
                imagens_conferencia = self._recortar_para_conferencia(lista_imagens)
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
                resposta_chaves = await cliente.chat.completions.create(
                    model=self.nome_modelo,
                    messages=[{"role": "user", "content": req_chaves}],
                    temperature=0,
                    timeout=60.0,
                )
                texto_chaves = resposta_chaves.choices[0].message.content or ""
                dados_chaves = self._limpar_e_converter_json(
                    texto_chaves,
                    conteudo_arquivo=conteudo_arquivo,
                    nome_arquivo=nome_arquivo,
                    texto_documento=texto_pdf,
                )
                self._mesclar_conferencia(dados_dict, dados_chaves)
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
        """Recorta topo e rodapé para ampliar os campos pequenos da DANFE."""

        recortes: list[tuple[str, bytes]] = []
        for numero_pagina, imagem_bytes in enumerate(imagens, start=1):
            imagem = Image.open(io.BytesIO(imagem_bytes)).convert("RGB")
            largura, altura = imagem.size
            regioes = (
                ("TOPO", (0, 0, largura, int(altura * 0.70))),
                ("RODAPÉ", (0, int(altura * 0.60), largura, altura)),
            )
            for nome_regiao, caixa in regioes:
                buffer = io.BytesIO()
                imagem.crop(caixa).save(
                    buffer,
                    format="JPEG",
                    quality=92,
                    optimize=True,
                )
                recortes.append(
                    (f"PÁGINA {numero_pagina} — {nome_regiao}:", buffer.getvalue())
                )
        return recortes

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
