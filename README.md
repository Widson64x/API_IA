# API de Extração de Dados de DANFE com IA Multi-Provedor

API em Python desenvolvida com FastAPI para recepção de Documentos Auxiliares da Nota Fiscal Eletrônica (DANFE) em formato PDF ou Imagem (PNG, JPG, WEBP) e extração de dados estruturados utilizando Inteligência Artificial (Google Gemini, OpenAI GPT, Anthropic Claude, DeepSeek e OpenRouter).

O sistema conta com um módulo robusto de **Autenticação e Administração de Clientes**, garantindo acesso seguro via JSON Web Tokens (JWT) e controle de tráfego por limites de requisição (Rate Limiting).

---

## Estrutura de Autenticação e Segurança

A API protege a extração de dados através de credenciais granulares:

1. **Camada Administrativa**: Endpoints de criação de clientes protegidos por uma chave mestra estática (`ADMIN_API_KEY`).
2. **Camada de Consumo (Clientes)**: Clientes geram sua própria **API Key** uma única vez e a utilizam para solicitar Tokens Temporários (JWT).
3. **Controle de Abuso**: Implementação de `Rate Limiting` (60 requisições por minuto por padrão).
4. **Segurança de Armazenamento**: Apenas o hash seguro (SHA-256 + Bcrypt) das chaves de API fica armazenado no banco de dados SQLite.

Para instruções completas de como gerar tokens e utilizar as rotas como cliente ou administrador, leia a documentação dedicada:
👉 **[Guia de Uso da API (Autenticação e Extração)](Docs/GUIA_DE_USO_API.md)**

---

## Arquitetura de IA (Extração)

O sistema utiliza os padrões de projeto **Strategy** e **Factory** para isolar a lógica dos provedores de IA:

- **`DANFEExtratorBase`**: Classe abstrata contendo o contrato de extração, utilitários para conversão de PDF em imagens via PyMuPDF e higienização de JSON.
- **`ExtratorGemini`**: Implementação baseada no SDK oficial Google GenAI (`gemini-2.5-flash` e `gemini-1.5-flash`).
- **`ExtratorOpenAI`**: Implementação utilizando o SDK AsyncOpenAI com capacidades de visão e JSON mode (`gpt-4o-mini`, `gpt-4o`).
- **`ExtratorClaude`**: Implementação via SDK AsyncAnthropic (`claude-3-5-sonnet`).
- **`ExtratorDeepSeek`**: Implementação via SDK OpenAI com suporte a endpoint nativo DeepSeek ou roteador OpenRouter (permite uso de modelos com camada gratuita).
- **`ExtratorFabrica`**: Fábrica estática que instancia dinamicamente o extrator desejado a partir do parâmetro `modelo_ia` fornecido na requisição HTTP.

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

### 3. Gerador de Chaves de Segurança Mestre

Para criar suas variáveis seguras de sistema (`SECRET_KEY` para geração de tokens JWT e `ADMIN_API_KEY` para gerenciamento), execute o assistente interativo:

```bash
python Scripts/GerarChaves.py
```
Esse utilitário criará credenciais robustas a partir da palavra-chave que você inserir e opcionalmente atualizará o arquivo `.env` para você de forma automática.

### 4. Configuração do Arquivo `.env`

Copie o arquivo `.env.example` para `.env` (caso o script acima já não o tenha feito) e insira as chaves dos provedores de IA que deseja utilizar e as chaves de segurança geradas:

```bash
cp .env.example .env
```

Conteúdo do `.env`:

```env
# Banco e Infra
HOST=0.0.0.0
PORT=8000
DEBUG=True
DB_URL=sqlite:///Data/IDocs.db

# Seguranca (gere utilizando Scripts/GerarChaves.py)
SECRET_KEY=sua_chave_jwt_aqui
ADMIN_API_KEY=sua_chave_admin_aqui

# APIs de IA
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

Acesse a documentação interativa Swagger UI em:
`http://localhost:8000/docs`

---

## Testes Automatizados

O sistema conta com rotinas de testes completas para garantir o funcionamento seguro:

**Testar Autenticação e Segurança:**
```bash
python Tests/TestarAutenticacao.py
```

**Testar Extração de DANFE (TestClient):**
Pode-se processar pastas inteiras de DANFEs, gerando um relatório em JSON para medir assertividade dos diferentes provedores de IA.

```bash
python Tests/TestClient.py --pasta caminho/para/pasta_danfes --modelo gemini-flash
```
