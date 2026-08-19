# Guia de Uso da API (Autenticação e Extração)

Este documento detalha o fluxo de operação da API IDocs_IA, tanto para administradores do sistema quanto para clientes finais que consumirão os endpoints de extração.

---

## 1. Visão Geral da Segurança

A API IDocs_IA é protegida por um sistema de dupla camada:
1. **Administração (`ADMIN_API_KEY`)**: Utilizada exclusivamente para o gerenciamento de clientes.
2. **Consumo (`JWT Access Token`)**: Utilizado pelos clientes para consumir os recursos da API (ex: extração de DANFE).

---

## 2. Fluxo do Administrador

Como administrador da plataforma, seu papel é cadastrar as empresas/sistemas que utilizarão a API.

### Passo 2.1: Cadastrar um Novo Cliente

Você precisa enviar uma requisição para a rota de administração informando o nome do cliente. O cabeçalho deve conter a sua chave mestre (`ADMIN_API_KEY` configurada no arquivo `.env`).

**Endpoint**: `POST /api/v1/admin/clientes`

**Headers**:
```http
x-admin-key: SUA_ADMIN_API_KEY_AQUI
Content-Type: application/json
```

**Body**:
```json
{
  "nome": "Sistema ERP Central",
  "descricao": "Integração de extração de notas fiscais"
}
```

**Resposta de Sucesso**:
```json
{
  "mensagem": "Cliente criado com sucesso. Guarde a API Key, ela nao sera exibida novamente.",
  "cliente_id": "cli_123456789",
  "api_key": "IDOCS-abc123def456..."
}
```

> [!WARNING]
> **Atenção**: O valor retornado no campo `api_key` só é exibido **uma única vez**. Copie e repasse esta chave de forma segura para o cliente que fará a integração.

---

## 3. Fluxo do Cliente (Usuário da API)

Como cliente (desenvolvedor ou sistema integrador), você recebeu uma **API Key** do administrador. Você não utilizará essa chave diretamente para fazer extrações. Primeiro, você deve trocá-la por um **Token de Acesso (JWT)**.

### Passo 3.1: Obter Token de Acesso (Autenticação)

Utilize sua API Key para solicitar um token temporário. Esse token padrão dura 60 minutos.

**Endpoint**: `POST /api/v1/auth/token`

**Headers**:
```http
Content-Type: application/json
```

**Body (JSON)**:
```json
{
  "api_key": "IDOCS-abc123def456..."
}
```

> [!TIP]
> **Como testar no Swagger:** Na rota `POST /api/v1/auth/token`, clique em "Try it out", coloque a sua `api_key` gerada no passo anterior dentro do JSON no campo `Request body` e clique em Execute. Copie o valor do `access_token` que for retornado na resposta, suba a página até o botão **"Authorize"** e cole APENAS esse token gigante lá dentro.

**Resposta de Sucesso**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1...",
  "refresh_token": "eyJhbGciOiJIUzI1...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Passo 3.2: Consumir a API (Extração de DANFE)

Agora que você possui o `access_token`, você deve enviá-lo no cabeçalho `Authorization` nas requisições para a API.

**Endpoint**: `POST /api/v1/danfe/extrair`

**Headers**:
```http
Authorization: Bearer eyJhbGciOiJIUzI1...
Content-Type: multipart/form-data
```

**Body (Form Data)**:
- `file`: (Arquivo binário PDF ou Imagem da DANFE)
- `modelo_ia`: `gemini-flash` (ou o modelo contratado)

**Exemplo em cURL**:
```bash
curl -X POST "http://localhost:8000/api/v1/danfe/extrair" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1..." \
  -H "Content-Type: multipart/form-data" \
  -F "file=@caminho/para/danfe.pdf" \
  -F "modelo_ia=gemini-flash"
```

### Passo 3.3: Renovar o Token de Acesso (Refresh)

Quando seu token de acesso expirar, você pode utilizar o `refresh_token` para obter um novo acesso sem precisar reenviar sua API Key. O token de atualização é válido por 7 dias.

**Endpoint**: `POST /api/v1/auth/refresh`

**Headers**:
```http
Authorization: Bearer SEU_REFRESH_TOKEN_AQUI
```

**Resposta de Sucesso**: Retorna novos tokens, idêntico ao passo 3.1.

---

## 4. Dúvidas Comuns

**O que acontece se eu fizer muitas requisições?**
A API conta com proteção de *Rate Limiting*. O padrão permite 60 requisições por minuto por cliente. Se ultrapassar, a API retornará o status `429 Too Many Requests`.

**Perdi minha API Key, e agora?**
O administrador do sistema não consegue recuperar a chave antiga. Será necessário revogar a antiga (ou deletar o cliente) e gerar uma nova credencial no endpoint de administração.
