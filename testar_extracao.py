import asyncio
import json
from App.Services.OpenRouterExtractorService import ExtratorOpenRouter

async def main():
    print("Iniciando teste de extração utilizando a API do OpenRouter (modelos vision gratuitos)...")
    # Utiliza o OpenRouter que detecta automaticamente modelos vision gratuitos disponíveis
    extrator = ExtratorOpenRouter()
    
    # Lendo o modelo de PDF
    caminho_pdf = "Data/input/63691.PDF"
    try:
        with open(caminho_pdf, "rb") as f:
            conteudo = f.read()
    except FileNotFoundError:
        print(f"Erro: Arquivo não encontrado em {caminho_pdf}")
        return
        
    print(f"Enviando '{caminho_pdf}' para a API (Isso pode demorar alguns segundos)...")
    try:
        resultado = await extrator.extrair_dados(conteudo, "63691.PDF")
        print("\n=== EXTRAÇÃO CONCLUÍDA ===")
        print(resultado.model_dump_json(indent=2))
        
        # Salvando o resultado para facilitar a leitura
        with open("resultado_teste.json", "w", encoding="utf-8") as out:
            out.write(resultado.model_dump_json(indent=2))
        print("\nO resultado também foi salvo no arquivo 'resultado_teste.json'.")
            
    except Exception as e:
        print(f"\n=== ERRO DURANTE A EXTRAÇÃO ===")
        print(str(e))

if __name__ == "__main__":
    asyncio.run(main())
