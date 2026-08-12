# API de Extração de Dados de DANFE com IA Multi-Provedor

API em Python desenvolvida com FastAPI para recepção de Documentos Auxiliares da Nota Fiscal Eletrônica (DANFE) em formato PDF ou Imagem (PNG, JPG, WEBP) e extração de dados estruturados utilizando Inteligência Artificial (Google Gemini, OpenAI GPT, Anthropic Claude, DeepSeek e OpenRouter).

---

## Arquitetura da Solução

O sistema utiliza os padrões de projeto **Strategy** e **Factory** para isolar a lógica dos provedores de IA:

- **`DANFEExtratorBase`**: Classe abstrata contendo o contrato de extração, utilitários para conversão de PDF em imagens via PyMuPDF e higienização de JSON.
- **`ExtratorGemini`**: Implementação baseada no SDK oficial Google GenAI (`gemini-2.5-flash` e `gemini-1.5-flash`).
- **`ExtratorOpenAI`**: Implementação utilizando o SDK AsyncOpenAI com capacidades de visão e JSON mode (`gpt-4o-mini`, `gpt-4o`).
- **`ExtratorClaude`**: Implementação via SDK AsyncAnthropic (`claude-3-5-sonnet`).
- **`ExtratorDeepSeek`**: Implementação via SDK OpenAI com suporte a endpoint nativo DeepSeek ou roteador OpenRouter (permite uso de modelos com camada gratuita).
- **`ExtratorFabrica`**: Fábrica estática que instancia dinamicamente o extrator desejado a partir do parâmetro `modelo_ia` fornecido na requisição HTTP.

---

## Estrutura do Projeto

```
IDocs_IA/
├── App/
│   ├── __init__.py
│   ├── Main.py                          # Ponto de entrada da aplicação FastAPI
│   ├── Core/
│   │   ├── __init__.py
│   │   └── Config.py                    # Gerenciador de configurações Pydantic Settings
│   ├── Schemas/
│   │   ├── __init__.py
│   │   └── DanfeSchema.py               # Schemas Pydantic para DANFE e respostas da API
│   ├── Services/
│   │   ├── __init__.py
│   │   ├── BaseExtractorService.py      # Classe abstrata DANFEExtratorBase
│   │   ├── GeminiExtractorService.py    # Extrator Gemini Flash
│   │   ├── OpenAIExtractorService.py    # Extrator OpenAI GPT-4o
│   │   ├── ClaudeExtractorService.py    # Extrator Anthropic Claude
│   │   ├── DeepSeekExtractorService.py  # Extrator DeepSeek / OpenRouter
│   │   └── ExtractorFactory.py          # Fábrica de extratores
│   └── Routers/
│       ├── __init__.py
│       └── DanfeRouter.py               # Endpoint POST /api/v1/danfe/extrair
├── Tests/
│   ├── __init__.py
│   └── TestClient.py                    # Cliente de teste em lote ou arquivo único
├── .env.example                         # Exemplo de configuração de chaves de API
├── .gitignore                           # Ignorados do versionador
├── requirements.txt                     # Lista de dependências Python
└── README.md                            # Documentação do projeto
```

---

## Configuração do Ambiente

### 1. Pré-requisitos
- Python 3.10 ou superior.

### 2. Instalação das Dependências

Crie um ambiente virtual (recomendado) e instale os pacotes:

```bash
python -m venv .venv
# Ativação no Windows PowerShell:
.venv\Scripts\Activate.ps1

# Instalação das dependências
pip install -r requirements.txt
```

### 3. Configuração do Arquivo `.env`

Copie o arquivo `.env.example` para `.env` e insira as chaves dos provedores que deseja utilizar:

```bash
cp .env.example .env
```

Conteúdo do `.env`:

```env
HOST=0.0.0.0
PORT=8000
DEBUG=True

GEMINI_API_KEY=sua_chave_gemini_aqui
OPENAI_API_KEY=sua_chave_openai_aqui
ANTHROPIC_API_KEY=sua_chave_claude_aqui
DEEPSEEK_API_KEY=sua_chave_deepseek_aqui
OPENROUTER_API_KEY=sua_chave_openrouter_aqui
```

---

## Execução da API

Para iniciar o servidor HTTP:

```bash
python -m App.Main
```

Ou através do Uvicorn diretamente:

```bash
uvicorn App.Main:app --reload --host 0.0.0.0 --port 8000
```

Acesse a documentação interativa Swagger UI em:
`http://localhost:8000/docs`

---

## Uso da API (Endpoints)

### `POST /api/v1/danfe/extrair`

Requisita a extração dos dados de uma DANFE.

#### Parâmetros da Requisição (Form Data / Multipart):
- **`file`** (Arquivo binário): Arquivo da DANFE (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`).
- **`modelo_ia`** (Texto): Identificador do modelo de IA a ser utilizado. Opções aceitas:
  - `gemini-flash` (Padrão)
  - `gpt-4o-mini`
  - `gpt-4o`
  - `claude-3-5-sonnet`
  - `deepseek-chat`
  - `openrouter-free`

#### Exemplo de Chamada cURL:

```bash
curl -X POST "http://localhost:8000/api/v1/danfe/extrair" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@caminho/para/danfe.pdf" \
  -F "modelo_ia=gemini-flash"
```

---

## Testes e Relatório de Assertividade

Foi desenvolvido um script dedicado em `Tests/TestClient.py` para testes avulsos e em lote (processamento de pastas inteiras de DANFEs).

### Executar modo interativo:
```bash
python Tests/TestClient.py
```

### Executar via linha de comando para um arquivo específico:
```bash
python Tests/TestClient.py --arquivo caminho/para/danfe.pdf --modelo gpt-4o-mini
```

### Executar para uma pasta inteira de DANFEs:
```bash
python Tests/TestClient.py --pasta caminho/para/pasta_danfes --modelo gemini-flash
```

Ao processar uma pasta, o cliente gerará uma tabela com os dados extraídos no terminal e salvará o resultado detalhado em JSON no diretório `Tests/Relatorios/`, permitindo comparar acurácia, tempo de resposta e assertividade dos modelos.
