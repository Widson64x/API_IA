import asyncio
from App.Services.OpenRouterExtractorService import ExtratorOpenRouter
from App.Services.GeminiExtractorService import ExtratorGemini

async def testar():
    caminho = r"C:\Applications\Python\Projetos\API_IA\Data\Model\63691.PDF"
    try:
        print("\n=== TESTE DIRETO SEM PASSAR PELA API ===")
        print("Lendo PDF...")
        with open(caminho, "rb") as f:
            conteudo = f.read()
        print(f"PDF lido. Tamanho: {len(conteudo)} bytes")
        
        print("\n--- Testando OpenRouter ---")
        extrator_or = ExtratorOpenRouter()
        try:
            dados = await extrator_or.extrair_dados(conteudo, "63691.PDF")
            print("\n✅ SUCESSO OPENROUTER!")
            print(dados.model_dump_json(indent=2))
            return
        except Exception as e_or:
            print(f"\n❌ ERRO OPENROUTER: {e_or}")
            
        print("\n--- Testando Gemini 2.5 Flash ---")
        extrator_gemini = ExtratorGemini(nome_modelo="gemini-2.5-flash")
        try:
            dados = await extrator_gemini.extrair_dados(conteudo, "63691.PDF")
            print("\n✅ SUCESSO GEMINI!")
            print(dados.model_dump_json(indent=2))
        except Exception as e_gem:
            print(f"\n❌ ERRO GEMINI: {e_gem}")

    except Exception as e:
        print(f"Erro fatal: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(testar())
