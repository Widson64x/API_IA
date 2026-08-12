"""Serviço responsável pela conversão e persistência de dados de DANFE em formatos JSON e XML.

Realiza a construção de documentos XML no padrão NFe em código Python,
economizando tokens da IA ao não solicitar a geração de formatação XML pela LLM.
"""

import json
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.dom import minidom

from App.Core.Config import configuracao
from App.Schemas.DanfeSchema import DadosDANFE


class ServidorGeracaoArquivos:
    """Classe utilitária para conversão e salvamento de arquivos JSON e XML de DANFE."""

    @staticmethod
    def _limpar_texto_xml(valor) -> str:
        """Higieniza valores antes da inclusão nas tags XML para evitar saída da string 'null'.

        Args:
            valor: Valor lido do modelo.

        Returns:
            str: String limpa ou vazia.
        """
        if valor is None:
            return ""
        val_str = str(valor).strip()
        if val_str.lower() in ("null", "none", "n/a"):
            return ""
        return val_str

    @classmethod
    def gerar_xml_danfe(cls, dados: DadosDANFE) -> str:
        """Gera a estrutura de texto XML baseada nos dados extraídos da DANFE.

        Args:
            dados (DadosDANFE): Objeto Pydantic com todas as informações extraídas da nota.

        Returns:
            str: String formatada contendo o código XML da NFe.
        """
        import re

        raiz = ET.Element("nfeProc", attrib={"xmlns": "http://www.portalfiscalsenef.fazenda.gov.br/nfe", "versao": "4.00"})
        nfe = ET.SubElement(raiz, "NFe")
        
        # Remove qualquer formatação (espaços, traços, pontos) da chave de acesso para manter estritamente os 44 dígitos no atributo Id
        chave_bruta = dados.chave_acesso or ""
        chave_numerica = re.sub(r"\D", "", str(chave_bruta))
        inf_nfe = ET.SubElement(nfe, "infNFe", attrib={"Id": f"NFe{chave_numerica}", "versao": "4.00"})

        # Dados de identificação (ide)
        ide = ET.SubElement(inf_nfe, "ide")
        ET.SubElement(ide, "nNF").text = cls._limpar_texto_xml(dados.numero_nota)
        ET.SubElement(ide, "serie").text = cls._limpar_texto_xml(dados.serie)
        ET.SubElement(ide, "natOp").text = cls._limpar_texto_xml(dados.natureza_operacao)
        ET.SubElement(ide, "tpNF").text = cls._limpar_texto_xml(dados.tipo_operacao or "1")
        ET.SubElement(ide, "dhEmi").text = cls._limpar_texto_xml(dados.data_emissao)
        ET.SubElement(ide, "dhSaiEnt").text = cls._limpar_texto_xml(dados.data_saida_entrada)

        # Emitente (emit)
        if dados.emitente:
            emit = ET.SubElement(inf_nfe, "emit")
            ET.SubElement(emit, "xNome").text = cls._limpar_texto_xml(dados.emitente.razao_social)
            ET.SubElement(emit, "xFant").text = cls._limpar_texto_xml(dados.emitente.nome_fantasia)
            ET.SubElement(emit, "CNPJ").text = cls._limpar_texto_xml(dados.emitente.cnpj)
            ET.SubElement(emit, "IE").text = cls._limpar_texto_xml(dados.emitente.inscricao_estadual)
            
            ender_emit = ET.SubElement(emit, "enderEmit")
            ET.SubElement(ender_emit, "xLgr").text = cls._limpar_texto_xml(dados.emitente.endereco)
            ET.SubElement(ender_emit, "xBairro").text = cls._limpar_texto_xml(dados.emitente.bairro)
            ET.SubElement(ender_emit, "xMun").text = cls._limpar_texto_xml(dados.emitente.municipio)
            ET.SubElement(ender_emit, "UF").text = cls._limpar_texto_xml(dados.emitente.uf)
            ET.SubElement(ender_emit, "CEP").text = cls._limpar_texto_xml(dados.emitente.cep)

        # Destinatário (dest)
        if dados.destinatario:
            dest = ET.SubElement(inf_nfe, "dest")
            ET.SubElement(dest, "xNome").text = cls._limpar_texto_xml(dados.destinatario.razao_social)
            ET.SubElement(dest, "CNPJ").text = cls._limpar_texto_xml(dados.destinatario.cnpj_cpf)
            ET.SubElement(dest, "IE").text = cls._limpar_texto_xml(dados.destinatario.inscricao_estadual)
            
            ender_dest = ET.SubElement(dest, "enderDest")
            ET.SubElement(ender_dest, "xLgr").text = cls._limpar_texto_xml(dados.destinatario.endereco)
            ET.SubElement(ender_dest, "xBairro").text = cls._limpar_texto_xml(dados.destinatario.bairro)
            ET.SubElement(ender_dest, "xMun").text = cls._limpar_texto_xml(dados.destinatario.municipio)
            ET.SubElement(ender_dest, "UF").text = cls._limpar_texto_xml(dados.destinatario.uf)
            ET.SubElement(ender_dest, "CEP").text = cls._limpar_texto_xml(dados.destinatario.cep)

        # Totais (total)
        if dados.valores_totais:
            total = ET.SubElement(inf_nfe, "total")
            icms_tot = ET.SubElement(total, "ICMSTot")
            ET.SubElement(icms_tot, "vBC").text = f"{dados.valores_totais.base_calculo_icms:.2f}"
            ET.SubElement(icms_tot, "vICMS").text = f"{dados.valores_totais.valor_icms:.2f}"
            ET.SubElement(icms_tot, "vBCST").text = f"{dados.valores_totais.base_calculo_icms_st:.2f}"
            ET.SubElement(icms_tot, "vST").text = f"{dados.valores_totais.valor_icms_st:.2f}"
            ET.SubElement(icms_tot, "vProd").text = f"{dados.valores_totais.valor_total_produtos:.2f}"
            ET.SubElement(icms_tot, "vFrete").text = f"{dados.valores_totais.valor_frete:.2f}"
            ET.SubElement(icms_tot, "vSeg").text = f"{dados.valores_totais.valor_seguro:.2f}"
            ET.SubElement(icms_tot, "vDesc").text = f"{dados.valores_totais.desconto:.2f}"
            ET.SubElement(icms_tot, "vII").text = "0.00"
            ET.SubElement(icms_tot, "vIPI").text = f"{dados.valores_totais.valor_ipi:.2f}"
            ET.SubElement(icms_tot, "vNF").text = f"{dados.valores_totais.valor_total_nota:.2f}"

        # Transportador (transp)
        if dados.transportador:
            transp = ET.SubElement(inf_nfe, "transp")
            transporta = ET.SubElement(transp, "transporta")
            ET.SubElement(transporta, "xNome").text = cls._limpar_texto_xml(dados.transportador.razao_social)
            ET.SubElement(transporta, "CNPJ").text = cls._limpar_texto_xml(dados.transportador.cnpj_cpf)
            ET.SubElement(transporta, "IE").text = cls._limpar_texto_xml(dados.transportador.inscricao_estadual)
            
            veic_transp = ET.SubElement(transp, "veicTransp")
            ET.SubElement(veic_transp, "placa").text = cls._limpar_texto_xml(dados.transportador.placa_veiculo)
            ET.SubElement(veic_transp, "UF").text = cls._limpar_texto_xml(dados.transportador.uf_veiculo)

        # Itens (det)
        for i, item in enumerate(dados.itens, start=1):
            det = ET.SubElement(inf_nfe, "det", attrib={"nItem": str(i)})
            prod = ET.SubElement(det, "prod")
            ET.SubElement(prod, "cProd").text = cls._limpar_texto_xml(item.codigo_produto)
            ET.SubElement(prod, "xProd").text = cls._limpar_texto_xml(item.descricao)
            ET.SubElement(prod, "NCM").text = cls._limpar_texto_xml(item.ncm_sh)
            ET.SubElement(prod, "CFOP").text = cls._limpar_texto_xml(item.cfop)
            ET.SubElement(prod, "uCom").text = cls._limpar_texto_xml(item.unidade or "UN")
            ET.SubElement(prod, "qCom").text = f"{item.quantidade:.4f}"
            ET.SubElement(prod, "vUnCom").text = f"{item.valor_unitario:.4f}"
            ET.SubElement(prod, "vProd").text = f"{item.valor_total:.2f}"

            imposto = ET.SubElement(det, "imposto")
            icms = ET.SubElement(imposto, "ICMS")
            icms_sn = ET.SubElement(icms, "ICMSSN102")
            ET.SubElement(icms_sn, "orig").text = "0"
            ET.SubElement(icms_sn, "CSOSN").text = cls._limpar_texto_xml(item.cst_csosn) or "102"

        # Converte para string formatada bonita com minidom
        string_bruta = ET.tostring(raiz, encoding="utf-8")
        dom_parsed = minidom.parseString(string_bruta)
        return dom_parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

    @classmethod
    def salvar_arquivos_saida(cls, dados: DadosDANFE, nome_arquivo_original: str, diretorio_saida: Path = None) -> dict:
        """Salva os arquivos JSON e XML extraídos da DANFE no diretório Data/output.

        Args:
            dados (DadosDANFE): Objeto com os dados extraídos.
            nome_arquivo_original (str): Nome do arquivo fonte enviado.
            diretorio_saida (Path, optional): Diretório onde salvar os arquivos. Padrão Data/output.

        Returns:
            dict: Dicionário contendo os caminhos absolutos dos arquivos JSON e XML gerados.
        """
        if diretorio_saida is None:
            diretorio_saida = configuracao.DIR_OUTPUT

        diretorio_saida.mkdir(parents=True, exist_ok=True)
        nome_base = Path(nome_arquivo_original).stem

        caminho_json = diretorio_saida / f"{nome_base}.json"
        caminho_xml = diretorio_saida / f"{nome_base}.xml"

        # 1. Salva o arquivo JSON
        conteudo_json = dados.model_dump_json(indent=2)
        with open(caminho_json, "w", encoding="utf-8") as file_json:
            file_json.write(conteudo_json)

        # 2. Salva o arquivo XML
        conteudo_xml = cls.gerar_xml_danfe(dados)
        with open(caminho_xml, "w", encoding="utf-8") as file_xml:
            file_xml.write(conteudo_xml)

        return {
            "caminho_json": str(caminho_json.absolute()),
            "caminho_xml": str(caminho_xml.absolute())
        }
