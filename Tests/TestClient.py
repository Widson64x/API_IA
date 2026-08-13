"""Cliente de teste em linha de comando para a API de Extração de DANFE.

Permite enviar documentos individuais (PDF ou Imagem) ou processar todos os arquivos
de uma pasta inteira. Oferece escolha de modelos de IA e salva relatórios em JSON.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
import requests
from tabulate import tabulate


class ClienteTesteDANFE:
    """Classe responsável por realizar chamadas de teste à API de extração de DANFE.

    Attributes:
        url_api (str): Endpoint completo da API para envio da requisição.
    """

    def __init__(self, url_base: str = "http://localhost:8000"):
        """Inicializa o cliente de testes.

        Args:
            url_base (str): URL base do servidor FastAPI. Padrão 'http://localhost:8000'.
        """
        self.url_api = f"{url_base.rstrip('/')}/api/v1/danfe/extrair"

    def enviar_documento(self, caminho_arquivo: str, modelo_ia: str = "gemini-flash") -> Dict[str, Any]:
        """Envia um único arquivo para a API e retorna o resultado da extração.

        Args:
            caminho_arquivo (str): Caminho absoluto ou relativo do arquivo a ser testado.
            modelo_ia (str): Nome do modelo de IA desejado. Padrão 'gemini-flash'.

        Returns:
            Dict[str, Any]: Dicionário com a resposta da API contendo sucesso, dados e metadados.
        """
        path_obj = Path(caminho_arquivo)
        if not path_obj.exists():
            print(f"[ERRO] Arquivo não encontrado: {caminho_arquivo}")
            return {"sucesso": False, "mensagem": "Arquivo não encontrado"}

        print(f"\n-> Processando arquivo: {path_obj.name} utilizando o modelo: '{modelo_ia}'...")
        
        tempo_inicio = time.time()
        
        try:
            with open(path_obj, "rb") as arquivo:
                arquivos = {"file": (path_obj.name, arquivo, "application/octet-stream")}
                dados_formulario = {"modelo_ia": modelo_ia}

                resposta = requests.post(self.url_api, files=arquivos, data=dados_formulario, timeout=300)
                tempo_decorrido = round(time.time() - tempo_inicio, 2)

                if resposta.status_code == 200:
                    resultado = resposta.json()
                    print(f"   Status: SUCESSO | Tempo cliente: {tempo_decorrido}s | Tempo API: {resultado.get('metadados', {}).get('tempo_execucao_segundos')}s")
                    return resultado
                else:
                    print(f"   Status: ERRO HTTP {resposta.status_code} | Resposta: {resposta.text}")
                    return {
                        "sucesso": False,
                        "mensagem": f"Erro HTTP {resposta.status_code}: {resposta.text}",
                        "nome_arquivo": path_obj.name
                    }

        except Exception as erro:
            print(f"   Status: EXCECAO | Erro: {str(erro)}")
            return {"sucesso": False, "mensagem": str(erro), "nome_arquivo": path_obj.name}

    def processar_diretorio(self, caminho_pasta: str, modelo_ia: str = "gemini-flash") -> List[Dict[str, Any]]:
        """Varre um diretório enviando todas as DANFEs encontradas (PDF, PNG, JPG, WEBP).

        Args:
            caminho_pasta (str): Caminho da pasta contendo os documentos.
            modelo_ia (str): Nome do modelo de IA.

        Returns:
            List[Dict[str, Any]]: Lista contendo os resultados de cada arquivo processado.
        """
        pasta_obj = Path(caminho_pasta)
        if not pasta_obj.exists() or not pasta_obj.is_dir():
            print(f"[ERRO] Pasta não encontrada ou inválida: {caminho_pasta}")
            return []

        extensoes_validas = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
        arquivos = [f for f in pasta_obj.iterdir() if f.suffix.lower() in extensoes_validas]

        if not arquivos:
            print(f"[AVISO] Nenhum arquivo com extensão válida ({', '.join(extensoes_validas)}) foi encontrado na pasta.")
            return []

        print(f"\n=======================================================")
        print(f"Iniciando lote de testes: {len(arquivos)} arquivo(s) na pasta: '{caminho_pasta}'")
        print(f"Modelo selecionado: {modelo_ia}")
        print(f"=======================================================")

        resultados = []
        for i, arquivo in enumerate(arquivos, start=1):
            print(f"\n[Item {i}/{len(arquivos)}]")
            resultado = self.enviar_documento(str(arquivo), modelo_ia=modelo_ia)
            resultados.append(resultado)

        self._gerar_relatorio_resumido(resultados)
        return resultados

    def _gerar_relatorio_resumido(self, resultados: List[Dict[str, Any]]) -> None:
        """Imprime uma tabela com os resultados consolidados do lote e salva um relatório JSON.

        Args:
            resultados (List[Dict[str, Any]]): Lista de respostas da API.
        """
        tabela = []
        sucessos = 0
        erros = 0

        for r in resultados:
            if r.get("sucesso"):
                sucessos += 1
                dados = r.get("dados", {})
                meta = r.get("metadados", {})
                tabela.append([
                    meta.get("nome_arquivo_original"),
                    dados.get("chave_acesso") or "N/A",
                    dados.get("numero_nota") or "N/A",
                    dados.get("emitente", {}).get("razao_social") or "N/A",
                    f"R$ {dados.get('valores_totais', {}).get('valor_total_nota', 0.0):.2f}",
                    f"{meta.get('tempo_execucao_segundos')}s",
                    "OK"
                ])
            else:
                erros += 1
                tabela.append([
                    r.get("nome_arquivo", "Desconhecido"),
                    "N/A", "N/A", "N/A", "N/A", "N/A", "FALHA"
                ])

        headers = ["Arquivo", "Chave de Acesso", "Número", "Emitente", "Valor Total", "Tempo", "Status"]
        print("\n" + tabulate(tabela, headers=headers, tablefmt="grid"))
        print(f"\nResumo da execução: Total: {len(resultados)} | Sucesso: {sucessos} | Falhas: {erros}")

        # Salva o resultado detalhado em formato JSON nas pastas Data/output e Tests/Relatorios
        pasta_relatorios = Path(__file__).parent / "Relatorios"
        pasta_output = Path(__file__).parent.parent / "Data" / "output"
        pasta_relatorios.mkdir(exist_ok=True)
        pasta_output.mkdir(exist_ok=True)
        
        caminho_relatorio = pasta_relatorios / f"relatorio_execucao_{int(time.time())}.json"
        caminho_relatorio_output = pasta_output / f"relatorio_lote_ultimo_teste.json"
        
        with open(caminho_relatorio, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)

        with open(caminho_relatorio_output, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)

        print(f"Relatório detalhado salvo em: {caminho_relatorio.absolute()}")
        print(f"Relatório de lote salvo em: {caminho_relatorio_output.absolute()}")


def executar_cli():
    """Ponto de entrada da CLI para execução interativa ou via argumentos de linha de comando."""
    pasta_input_padrao = str(Path(__file__).parent.parent / "Data" / "input")

    parser = argparse.ArgumentParser(description="Cliente de teste para a API de Extração de DANFE.")
    parser.add_argument("--arquivo", "-f", type=str, help="Caminho de um arquivo de DANFE avulso para teste.")
    parser.add_argument("--pasta", "-d", type=str, default=pasta_input_padrao, help="Caminho da pasta contendo múltiplos arquivos de DANFE (Padrão: Data/input).")
    parser.add_argument("--modelo", "-m", type=str, default="gemini", help="Modelo de IA (gemini, openai, claude, openrouter, groq).")
    parser.add_argument("--url", "-u", type=str, default="http://localhost:8000", help="URL base da API FastAPI.")

    args = parser.parse_args()
    cliente = ClienteTesteDANFE(url_base=args.url)

    if args.arquivo:
        res = cliente.enviar_documento(args.arquivo, modelo_ia=args.modelo)
        print("\nJSON de Resposta Completo:")
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.pasta:
        cliente.processar_diretorio(args.pasta, modelo_ia=args.modelo)
    else:
        # Modo interativo se nenhum argumento for passado
        print("=== CLIENTE DE TESTE DE EXTRAÇÃO DE DANFE ===")
        print("1. Enviar um único arquivo (PDF ou Imagem)")
        print(f"2. Enviar todos os arquivos da pasta padrão ({pasta_input_padrao})")
        print("3. Digitar o caminho de outra pasta")
        opcao = input("\nEscolha a opção (1, 2 ou 3): ").strip()

        modelo = input("Digite o modelo de IA (Padrão: gemini-flash) [gemini-flash/gpt-4o-mini/claude-3-5-sonnet/deepseek-chat]: ").strip()
        if not modelo:
            modelo = "gemini-flash"

        if opcao == "1":
            caminho = input("Digite o caminho do arquivo: ").strip().strip('"')
            res = cliente.enviar_documento(caminho, modelo_ia=modelo)
            print("\nJSON de Resposta Completo:")
            print(json.dumps(res, indent=2, ensure_ascii=False))
        elif opcao == "2":
            cliente.processar_diretorio(pasta_input_padrao, modelo_ia=modelo)
        elif opcao == "3":
            caminho = input("Digite o caminho da pasta: ").strip().strip('"')
            cliente.processar_diretorio(caminho, modelo_ia=modelo)
        else:
            print("Opção inválida.")


if __name__ == "__main__":
    executar_cli()
