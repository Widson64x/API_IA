"""Testes da reconciliação e validação dos dados de DANFE."""

import base64
import io
import unittest
from typing import Any

import pymupdf
import zxingcpp
from PIL import Image

from App import VERSAO_TUPLA, __version__
from App.Routers.DanfeRouter import _decodificar_arquivo_base64
from App.Schemas.DanfeSchema import DadosDANFE
from App.Services.BaseExtractorService import DANFEExtratorBase
from App.Services.MistralExtractorService import ExtratorMistral


class ExtratorTeste(DANFEExtratorBase):
    """Implementação mínima para exercitar as rotinas da classe base."""

    async def extrair_dados(
        self,
        conteudo_arquivo: bytes,
        nome_arquivo: str,
    ) -> DadosDANFE:
        raise NotImplementedError


class TesteExtracaoDANFE(unittest.TestCase):
    """Cobre as invariantes que impedem as falhas observadas nas amostras."""

    def setUp(self) -> None:
        self.extrator = ExtratorTeste()

    def test_versao_da_aplicacao_e_semantica(self) -> None:
        self.assertEqual(__version__, "2.0.1")
        self.assertEqual(VERSAO_TUPLA, (2, 0, 1))

    def test_base64_puro_e_data_url_sao_decodificados(self) -> None:
        conteudo = b"%PDF-1.7\nconteudo de teste"
        codificado = base64.b64encode(conteudo).decode("ascii")

        self.assertEqual(_decodificar_arquivo_base64(codificado), conteudo)
        self.assertEqual(
            _decodificar_arquivo_base64(
                f"data:application/pdf;base64,{codificado}"
            ),
            conteudo,
        )

    def test_base64_vazio_ou_invalido_e_rejeitado(self) -> None:
        valores_invalidos = (
            "",
            "%%%invalido%%%",
            "data:application/pdf,sem-base64",
            "data:application/pdf;base64,",
        )

        for valor in valores_invalidos:
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                _decodificar_arquivo_base64(valor)

    def test_chaves_reais_das_amostras_sao_validas(self) -> None:
        chaves = [
            "15260401206820002655550020000316791049620168",
            "32260355163042000216550010000047161323831584",
            "25260906626253149384550500000000101255550107",
            "42260553359824000542550010000210161965575801",
            "15260961585865288406550040003546441202609029",
            "42260853359824000542550010000225111464786288",
        ]
        self.assertTrue(
            all(self.extrator._chave_acesso_valida(chave) for chave in chaves)
        )

    def test_chave_corrige_numero_e_serie(self) -> None:
        chave = "15260401206820002655550020000316791049620168"
        bloco: dict[str, Any] = {
            "numero": "999",
            "serie": "999",
            "chave_acesso": chave,
        }
        self.extrator._normalizar_nota(bloco, chave)
        self.assertEqual(
            bloco,
            {"numero": "31679", "serie": "2", "chave_acesso": chave},
        )

    def test_devolucao_atual_fica_em_nfd_e_original_em_nfo(self) -> None:
        chave_devolucao = "25260906626253149384550500000000101255550107"
        chave_original = "42260553359824000542550010000210161965575801"
        texto = f"""
IDENTIFICAÇÃO DO EMITENTE
EMPREENDIMENTOS PAGUE MENOS SA
CNPJ 06.626.253/1493-84
CHAVE DE ACESSO {chave_devolucao}
NATUREZA DA OPERAÇÃO Estorno de NF-e
DESTINATÁRIO / REMETENTE
BLANVER FARMOQUIMICA E FARMACEUTICA S A
CNPJ / CPF 53.359.824/0005-42
CÁLCULO DO IMPOSTO
NFO 21016 EMISSAO 20/05/2026 Chave: {chave_original}
"""
        resposta_errada = {
            "arquivo": "inventado",
            "quantidade_nota": 9,
            "notaFiscalList": [
                {
                    "Remetente": {
                        "nome": "EMPREENDIMENTOS PAGUE MENOS SA",
                        "cnpj": "53.359.824/0005-42",
                        "cep": "N/A",
                    },
                    "Destinatario": {
                        "nome": "BLANVER FARMOQUIMICA E FARMACEUTICA S A",
                        "cnpj": "53.359.824/0005-42",
                    },
                    "NFO": {
                        "numero": "10",
                        "serie": "50",
                        "chave_acesso": chave_devolucao,
                        "peso": "0,380",
                        "volume": 0,
                        "valor": "59,78",
                    },
                    "NFD": {
                        "numero": "21016",
                        "serie": "2",
                        "chave_acesso": chave_original,
                        "peso": 0,
                        "valor": 0,
                    },
                    "pedido": "LOTE FRACIONADO",
                }
            ],
        }

        resultado = self.extrator._validar_e_corrigir_extracao(
            resposta_errada,
            texto_documento=texto,
            conteudo_arquivo=b"pdf",
            nome_arquivo="nf_10.PDF",
        )
        nota = resultado["notaFiscalList"][0]

        self.assertEqual(resultado["arquivo"], "nf_10")
        self.assertEqual(resultado["extensao"], "pdf")
        self.assertEqual(resultado["tamanho"], "3")
        self.assertEqual(resultado["quantidade_nota"], 1)
        self.assertEqual(nota["Remetente"]["cnpj"], "06626253149384")
        self.assertEqual(nota["Remetente"]["bairro"], "S/N")
        self.assertEqual(nota["Remetente"]["numero"], "S/N")
        self.assertEqual(nota["Destinatario"]["cnpj"], "53359824000542")
        self.assertEqual(nota["Destinatario"]["bairro"], "S/N")
        self.assertEqual(nota["Destinatario"]["numero"], "S/N")
        self.assertEqual(nota["NFD"]["numero"], "10")
        self.assertEqual(nota["NFD"]["serie"], "50")
        self.assertEqual(nota["NFD"]["chave_acesso"], chave_devolucao)
        self.assertEqual(nota["NFD"]["peso"], 0.38)
        self.assertEqual(nota["NFD"]["valor"], 59.78)
        self.assertEqual(nota["NFO"]["numero"], "21016")
        self.assertEqual(nota["NFO"]["serie"], "1")
        self.assertEqual(nota["NFO"]["chave_acesso"], chave_original)
        self.assertNotIn("peso", nota["NFO"])
        self.assertNotIn("valor", nota["NFO"])
        self.assertEqual(nota["pedido"], "LOTE FRACIONADO")

    def test_data_criacao_vem_dos_metadados_antes_da_quantidade(self) -> None:
        documento = pymupdf.open()
        documento.new_page()
        documento.set_metadata({"modDate": "D:20260918203635Z"})
        conteudo = documento.tobytes()
        documento.close()

        resultado = self.extrator._validar_e_corrigir_extracao(
            {"notaFiscalList": []},
            conteudo_arquivo=conteudo,
            nome_arquivo="nota.pdf",
        )

        self.assertEqual(resultado["data_criacao"], "2026-09-18")
        campos = list(resultado)
        self.assertLess(
            campos.index("data_criacao"),
            campos.index("quantidade_nota"),
        )

    def test_schema_mantem_bairro_e_numero_com_fallback(self) -> None:
        dados = DadosDANFE(
            quantidade_nota=1,
            notaFiscalList=[{"Remetente": {"nome": "Empresa"}}],
        )

        remetente = dados.model_dump(exclude_none=True)["notaFiscalList"][0][
            "Remetente"
        ]
        self.assertEqual(remetente["bairro"], "S/N")
        self.assertEqual(remetente["numero"], "S/N")

    def test_numero_da_nota_nao_e_reutilizado_como_pedido(self) -> None:
        resultado = self.extrator._validar_e_corrigir_extracao(
            {
                "notaFiscalList": [
                    {
                        "NFO": {"numero": "63107", "serie": "1"},
                        "pedido": "000063107",
                    }
                ]
            }
        )

        self.assertEqual(resultado["notaFiscalList"][0]["pedido"], "S/N")

    def test_nfo_referenciada_nao_repete_totais_da_nfd(self) -> None:
        resultado = self.extrator._validar_e_corrigir_extracao(
            {
                "notaFiscalList": [
                    {
                        "NFO": {
                            "numero": "63107",
                            "peso": 0.08,
                            "volume": 1,
                            "valor": 40.04,
                        },
                        "NFD": {
                            "numero": "31679",
                            "peso": 0.08,
                            "volume": 1,
                            "valor": 31.39,
                        },
                    }
                ]
            }
        )

        item = resultado["notaFiscalList"][0]
        self.assertEqual(item["NFO"], {"numero": "63107"})
        self.assertEqual(
            item["NFD"],
            {"numero": "31679", "peso": 0.08, "volume": 1.0, "valor": 31.39},
        )

    def test_conferencia_mistral_mescla_somente_chaves_validas(self) -> None:
        chave_nfd = "15260401206820002655550020000316791049620168"
        chave_nfo = "42260307591326000422550010000631071276480157"
        dados = {
            "notaFiscalList": [
                {
                    "NFO": {"numero": "63107", "serie": "1"},
                    "NFD": {"numero": "31679", "serie": "2"},
                }
            ]
        }
        texto = (
            '{"chaves": ['
            f'{{"numero": "31679", "chave_acesso": "{chave_nfd}{chave_nfd}"}},'
            f'{{"numero": "63107", "chave_acesso": "{chave_nfo}"}},'
            '{"numero": "31679", "chave_acesso": "1526040120"}'
            "]}"
        )

        ExtratorMistral._mesclar_chaves_do_texto(dados, texto)

        item = dados["notaFiscalList"][0]
        self.assertEqual(item["NFD"]["chave_acesso"], chave_nfd)
        self.assertEqual(item["NFO"]["chave_acesso"], chave_nfo)

    def test_conferencia_critica_corrige_bairro_e_peso_sem_dacte(self) -> None:
        extrator = ExtratorMistral()
        dados = {
            "notaFiscalList": [
                {
                    "Remetente": {
                        "cnpj": "01206820002655",
                        "endereco": "ROD BR 316 KM 23/24",
                        "bairro": "S/N",
                        "numero": "S/N",
                    },
                    "NFD": {"numero": "31679", "peso": 34.44},
                }
            ]
        }
        conferencia = {
            "notaFiscalList": [
                {
                    "Remetente": {
                        "cnpj": "01.206.820/0002-55",
                        "endereco": "ROD BR 316 KM 23/24, S/N - ITAPEPOCU",
                        "bairro": "ITAPEPOCU",
                        "numero": "S/N",
                    },
                    "NFD": {"numero": "31679", "peso": "0,080"},
                }
            ]
        }

        extrator._mesclar_campos_criticos(dados, conferencia)

        item = dados["notaFiscalList"][0]
        self.assertEqual(item["Remetente"]["endereco"], "ROD BR 316 KM 23/24")
        self.assertEqual(item["Remetente"]["bairro"], "ITAPEPOCU")
        self.assertEqual(item["Remetente"]["numero"], "S/N")
        self.assertEqual(item["NFD"]["peso"], 0.08)

    def test_chave_e_lida_diretamente_do_codigo_de_barras(self) -> None:
        chave = "15260401206820002655550020000316791049620168"
        codigo = zxingcpp.create_barcode(chave, zxingcpp.BarcodeFormat.Code128)
        imagem = Image.fromarray(codigo.to_image(scale=4))
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG")

        chaves = self.extrator._extrair_chaves_codigo_barras(
            buffer.getvalue(),
            "nota.png",
        )

        self.assertEqual(chaves, [chave])

    def test_descarta_chave_cnpj_e_campos_ausentes_invalidos(self) -> None:
        resultado = self.extrator._validar_e_corrigir_extracao(
            {
                "notaFiscalList": [
                    {
                        "Remetente": {"nome": "Empresa", "cnpj": "11111111111111"},
                        "NFO": {
                            "numero": "123456789012",
                            "chave_acesso": "1" * 44,
                            "data": "32/13/2026",
                            "peso": 0,
                            "volume": "N/A",
                        },
                    }
                ]
            }
        )
        nota = resultado["notaFiscalList"][0]
        self.assertEqual(
            nota["Remetente"],
            {"nome": "Empresa", "bairro": "S/N", "numero": "S/N"},
        )
        self.assertNotIn("NFO", nota)

    def test_modelo_omite_nulos_na_serializacao_publica(self) -> None:
        dados = DadosDANFE(
            arquivo="nota",
            extensao="pdf",
            tamanho="10",
            quantidade_nota=1,
            notaFiscalList=[{"NFD": {"numero": "1", "peso": None}}],
        )
        self.assertEqual(
            dados.model_dump(exclude_none=True),
            {
                "arquivo": "nota",
                "extensao": "pdf",
                "tamanho": "10",
                "quantidade_nota": 1,
                "notaFiscalList": [
                    {"NFD": {"numero": "1"}, "pedido": "S/N"}
                ],
            },
        )

    def test_prompt_nao_contem_dados_de_outras_notas(self) -> None:
        prompt = self.extrator._obter_prompt_instrucao()
        self.assertNotIn("2939107", prompt)
        self.assertNotIn("RANBAXY", prompt)
        self.assertNotIn("01.206.820/0015-00", prompt)
        self.assertIn("Ignore completamente DACTE", prompt)

    def test_nome_e_logradouro_sao_reconciliados_com_ocr(self) -> None:
        entidade = {
            "nome": "MOKSHAS BR IND E COM DE MEDICAMENTO",
            "cnpj": "07.591.326/0004-22",
            "endereco": "RGD BR 316, KM 25",
        }
        texto = """linha irrelevante
MOKSHA8 BR IND E COM DE MEDICAMENTO
outra linha"""

        self.extrator._normalizar_entidade(entidade, "")
        self.extrator._reconciliar_nome_com_ocr(entidade, texto)

        self.assertEqual(entidade["nome"], "MOKSHA8 BR IND E COM DE MEDICAMENTO")
        self.assertEqual(entidade["endereco"], "ROD BR 316, KM 25")

    def test_endereco_composto_separa_numero_e_bairro(self) -> None:
        casos = (
            "ROD BR 316 KM 23/24, S/N - ITAPEPOCU",
            "ROD BR 316 KM 23/24, ITAPEPOCU",
        )

        for endereco in casos:
            with self.subTest(endereco=endereco):
                entidade = {"nome": "Empresa", "endereco": endereco}
                self.extrator._normalizar_entidade(entidade, "")
                self.assertEqual(entidade["endereco"], "ROD BR 316 KM 23/24")
                self.assertEqual(entidade["numero"], "S/N")
                self.assertEqual(entidade["bairro"], "ITAPEPOCU")

    def test_ocr_corrige_chaves_nome_e_peso_da_31679(self) -> None:
        chave_devolucao = "15260401206820002655550020000316791049620168"
        chave_original = "42260307591326000422550010000631071276480157"
        texto_ocr = f"""
NATUREZA DA OPERAÇÃO Devolucao de compra para comercializacao
CHAVE DE ACESSO {chave_devolucao}
| NOME / RAZÃO SOCIAL MOKSHAS BR IND E COM DE MEDICAMENTO |
| QUANTIDADE 00001 | PESO BRUTO 0,080 | PESO LÍQUIDO 0,000 |
Dev. Ref. NF(s). 00063107 de 26/03/2026
NF-E: {chave_original}
MOKSHA8 BR IND E COM DE MEDICAMENTO
"""
        resultado = self.extrator._validar_e_corrigir_extracao(
            {
                "notaFiscalList": [
                    {
                        "Destinatario": {
                            "nome": "MOKSHAS BR IND E COM DE MEDICAMENTO",
                            "cnpj": "07.591.326/0004-22",
                        },
                        "NFO": {"numero": "63107", "serie": "1"},
                        "NFD": {
                            "numero": "31679",
                            "serie": "2",
                            "peso": 0.1148,
                        },
                    }
                ]
            },
            texto_documento=texto_ocr,
        )
        nota = resultado["notaFiscalList"][0]

        self.assertEqual(
            nota["Destinatario"]["nome"],
            "MOKSHA8 BR IND E COM DE MEDICAMENTO",
        )
        self.assertEqual(nota["NFD"]["chave_acesso"], chave_devolucao)
        self.assertEqual(nota["NFD"]["peso"], 0.08)
        self.assertEqual(nota["NFO"]["chave_acesso"], chave_original)

    def test_ocr_omite_peso_vazio_e_completa_chaves_da_104942(self) -> None:
        chave_devolucao = "15260461585865288406550040001049421202604159"
        chave_original = "32260355163042000216550010000047161323831584"
        texto_ocr = f"""
CHAVE DE ACESSO {chave_devolucao}
| QUANTIDADE 3 | NUMERAÇÃO | PESO BRUTO | | PESO LÍQUIDO |
N/Fe Ref.: Número 4716 Série 1 em 03/2026 ({chave_original})
"""
        resultado = self.extrator._validar_e_corrigir_extracao(
            {
                "notaFiscalList": [
                    {
                        "NFO": {"numero": "4716", "serie": "1"},
                        "NFD": {
                            "numero": "104942",
                            "serie": "4",
                            "peso": 3000,
                        },
                    }
                ]
            },
            texto_documento=texto_ocr,
        )
        nota = resultado["notaFiscalList"][0]

        self.assertEqual(nota["NFD"]["chave_acesso"], chave_devolucao)
        self.assertNotIn("peso", nota["NFD"])
        self.assertEqual(nota["NFO"]["chave_acesso"], chave_original)


if __name__ == "__main__":
    unittest.main()
