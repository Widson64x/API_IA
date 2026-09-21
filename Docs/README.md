# API_IA

[Voltar ao índice mestre](../../../Documentacao-Web/README.md)

## Finalidade

API FastAPI para receber DANFE em PDF/imagem e extrair dados estruturados com provedores de IA. Possui autenticação administrativa, credenciais por cliente, JWT e limite de requisições.

## Código e execução

- Repositório: `Widson64x/API_IA`
- Diretório local: `C:\Projetos\LUFT\Python\API_IA`
- Produção: `C:\ProjetosPython\API_IA`
- Entry point: `Asgi.py`/aplicação em `App`
- Stack: FastAPI, Uvicorn, SQLite para credenciais/metadados e SDKs dos provedores.
- Rotas principais: `/api/v1/admin`, `/api/v1/auth` e `/api/v1/danfe`.
- Guia de consumo: [GUIA_DE_USO_API.md](GUIA_DE_USO_API.md)

## Publicação

| Item | Valor |
|---|---|
| URL | `http://b2bi-apps.luftfarma.com.br/api-ia/` |
| Nginx | upstream `api_ia` |
| Porta | 9008 |
| `ROOT_PATH` | `/api-ia` |
| Serviço do workflow | `Luft-API-IA` |
| Runner | `runner-api-ia` em `C:\GitHubRunners\API_IA` |
| Branch | `main` |

A rota respondeu 200 em 14/09/2026. Não foi encontrado job de homologação.

## Configuração

Variáveis por categoria:

- HTTP: `HOST`, `PORT`, `ROOT_PATH`, `DEBUG`.
- JWT: `SECRET_KEY`, algoritmo e tempos de expiração.
- Administração: `ADMIN_API_KEY`.
- Limite: `RATE_LIMIT_REQUISICOES_POR_MINUTO`.
- Provedores: chaves Gemini, OpenAI, Anthropic, DeepSeek, OpenRouter e Mistral.

Todos os valores sensíveis devem vir de `.env` protegido ou mecanismo de segredos. O banco SQLite e arquivos enviados/gerados são dados persistentes e não podem ser apagados pela sincronização de deploy.

## Desenvolvimento

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m App.Main
```

Use documentos sintéticos ou anonimizados em testes. Não envie DANFE de produção a provedor externo sem base legal, contrato e política corporativa aprovados.

## Verificação

- Abra `/api-ia/docs` pelo proxy e confirme que URLs mantêm o prefixo.
- Gere token com cliente de teste.
- Processe arquivo sintético pequeno.
- Confirme rate limiting e rejeição de credencial inválida.
- Revise logs para garantir ausência de chave, JWT e conteúdo integral do documento.

Em caso de 404, compare `ROOT_PATH`, `X-Forwarded-Prefix` e configuração do Nginx. Em caso de 502, verifique `Luft-API-IA`, porta 9008 e startup do Uvicorn.
