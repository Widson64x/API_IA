# Guia de Uso da API (Autenticação, Extração e Exemplos de Código)

Este documento detalha o fluxo completo de integração com a **API IDocs_IA**, desde o cadastro e geração de tokens até exemplos práticos e prontos para uso nas principais linguagens de programação (**Python**, **C# / .NET**, **JavaScript / Node.js**, **cURL** e **PHP**).

---

## 1. Visão Geral da Segurança

A API IDocs_IA utiliza um modelo de segurança em duas camadas:
1. **Chave Administrativa (`ADMIN_API_KEY`)**: Utilizada exclusivamente por administradores para cadastrar clientes/sistemas.
2. **API Key do Cliente**: Utilizada pelo cliente para solicitar um **Token de Acesso JWT (Access Token)** temporário.
3. **Bearer Token JWT**: Enviado no cabeçalho `Authorization: Bearer <access_token>` de cada requisição para os endpoints de extração.

> [!NOTE]
> Os tokens JWT de acesso possuem validade padrão de **60 minutos**. Para renovar o acesso sem reenviar a API Key, utilize o `refresh_token` gerado durante a autenticação.

---

## 2. Fluxo de Autenticação (Obtenção de Token)

### 2.1 Requisição de Token
Para gerar o token de acesso, envie uma requisição HTTP POST para `/api/v1/auth/token` contendo sua `api_key`:

- **Endpoint**: `POST /api/v1/auth/token`
- **Header**: `Content-Type: application/json`
- **Body (JSON)**:
```json
{
  "api_key": "IDOCS-sua-chave-de-api-aqui"
}
```

- **Resposta de Sucesso (HTTP 200)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1Ni...",
  "refresh_token": "eyJhbGciOiJIUzI1Ni...",
  "token_type": "bearer",
  "expira_em_minutos": 60
}
```

---

## 3. Fluxo de Extração de DANFE

Para extrair os dados estruturados da DANFE (PDF ou Imagem PNG/JPG/WEBP):

- **Endpoint**: `POST /api/v1/danfe/extrair`
- **Headers**:
  - `Authorization: Bearer <access_token>`
  - `Content-Type: multipart/form-data`
- **Parâmetros do Formulário (Form-Data)**:
  - `file`: Arquivo da DANFE em formato PDF ou imagem (`png`, `jpg`, `jpeg`, `webp`).
  - `modelo_ia`: Modelo de IA a ser utilizado (`gemini`, `openai`, `claude`, `deepseek`). *(Opcional, padrão: `gemini`)*.

---

## 4. Exemplos de Integração por Linguagem

### 🐍 Python (com `requests`)

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"  # Ajuste para a URL do servidor
API_KEY = "IDOCS-sua-chave-aqui"

def obter_access_token(api_key: str) -> str:
    """Solicita um access token JWT utilizando a API Key do cliente."""
    url = f"{BASE_URL}/auth/token"
    resposta = requests.post(url, json={"api_key": api_key})
    resposta.raise_for_status()
    return resposta.json()["access_token"]

def extrair_danfe(access_token: str, caminho_pdf: str, modelo_ia: str = "gemini") -> dict:
    """Envia o arquivo DANFE para extração de dados via IA."""
    url = f"{BASE_URL}/danfe/extrair"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    with open(caminho_pdf, "rb") as arquivo:
        files = {"file": (caminho_pdf, arquivo, "application/pdf")}
        data = {"modelo_ia": modelo_ia}
        
        resposta = requests.post(url, headers=headers, files=files, data=data)
        resposta.raise_for_status()
        return resposta.json()

# Execução
if __name__ == "__main__":
    try:
        token = obter_access_token(API_KEY)
        print("✅ Token JWT obtido com sucesso.")

        resultado = extrair_danfe(token, "exemplo_danfe.pdf", modelo_ia="gemini")
        print("✅ Extração concluída:")
        print(f"Sucesso: {resultado['sucesso']}")
        print(f"Dados Extraídos: {resultado['dados']}")
    except Exception as erro:
        print(f"❌ Erro na requisição: {erro}")
```

---

### 🔷 C# / .NET (com `HttpClient`)

```csharp
using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

class Program
{
    private static readonly HttpClient client = new HttpClient();
    private const string BaseUrl = "http://localhost:8000/api/v1";
    private const string ApiKey = "IDOCS-sua-chave-aqui";

    static async Task Main(string[] args)
    {
        try
        {
            string token = await ObterAccessTokenAsync(ApiKey);
            Console.WriteLine("✅ Token JWT obtido com sucesso.");

            string resultadoJson = await ExtrairDanfeAsync(token, "exemplo_danfe.pdf", "gemini");
            Console.WriteLine("✅ Extração concluída:");
            Console.WriteLine(resultadoJson);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Erro: {ex.Message}");
        }
    }

    private static async Task<string> ObterAccessTokenAsync(string apiKey)
    {
        var url = $"{BaseUrl}/auth/token";
        var payload = JsonSerializer.Serialize(new { api_key = apiKey });
        var content = new StringContent(payload, Encoding.UTF8, "application/json");

        var response = await client.PostAsync(url, content);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);
        return doc.RootElement.GetProperty("access_token").GetString();
    }

    private static async Task<string> ExtrairDanfeAsync(string accessToken, string caminhoArquivo, string modeloIa = "gemini")
    {
        var url = $"{BaseUrl}/danfe/extrair";

        using var request = new HttpRequestMessage(HttpMethod.Post, url);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        using var form = new MultipartFormDataContent();
        byte[] fileBytes = await File.ReadAllBytesAsync(caminhoArquivo);
        var fileContent = new ByteArrayContent(fileBytes);
        fileContent.Headers.ContentType = MediaTypeHeaderValue.Parse("application/pdf");

        form.Add(fileContent, "file", Path.GetFileName(caminhoArquivo));
        form.Add(new StringContent(modeloIa), "modelo_ia");

        request.Content = form;

        var response = await client.SendAsync(request);
        response.EnsureSuccessStatusCode();

        return await response.Content.ReadAsStringAsync();
    }
}
```

---

### 🟨 JavaScript / Node.js (com `fetch` nativo)

```javascript
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://localhost:8000/api/v1';
const API_KEY = 'IDOCS-sua-chave-aqui';

// 1. Obter Token JWT
async function obterToken(apiKey) {
  const response = await fetch(`${BASE_URL}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey }),
  });

  if (!response.ok) {
    const erro = await response.text();
    throw new Error(`Erro ao obter token (${response.status}): ${erro}`);
  }

  const data = await response.json();
  return data.access_token;
}

// 2. Extrair DANFE (Node.js 18+ ou Browser)
async function extrairDanfe(accessToken, caminhoArquivo, modeloIa = 'gemini') {
  const fileBuffer = fs.readFileSync(caminhoArquivo);
  const blob = new Blob([fileBuffer], { type: 'application/pdf' });
  const filename = path.basename(caminhoArquivo);

  const formData = new FormData();
  formData.append('file', blob, filename);
  formData.append('modelo_ia', modeloIa);

  const response = await fetch(`${BASE_URL}/danfe/extrair`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const erro = await response.text();
    throw new Error(`Erro na extração (${response.status}): ${erro}`);
  }

  return await response.json();
}

// Execução
(async () => {
  try {
    const token = await obterToken(API_KEY);
    console.log('✅ Token JWT obtido.');

    const resultado = await extrairDanfe(token, './exemplo_danfe.pdf', 'gemini');
    console.log('✅ Dados Extraídos:', JSON.stringify(resultado, null, 2));
  } catch (error) {
    console.error('❌ Falha:', error.message);
  }
})();
```

---

### 💻 cURL (Terminal / Bash / PowerShell)

#### Passo 1: Obter o Access Token
```bash
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"api_key": "IDOCS-sua-chave-aqui"}'
```

#### Passo 2: Enviar DANFE para Extração
```bash
curl -X POST "http://localhost:8000/api/v1/danfe/extrair" \
  -H "Authorization: Bearer COPIE_O_ACCESS_TOKEN_AQUI" \
  -F "file=@exemplo_danfe.pdf" \
  -F "modelo_ia=gemini"
```

---

### 🐘 PHP (com `cURL` nativo)

```php
<?php

$baseUrl = "http://localhost:8000/api/v1";
$apiKey = "IDOCS-sua-chave-aqui";

// 1. Função para Obter Token
function obterToken($baseUrl, $apiKey) {
    $ch = curl_init("$baseUrl/auth/token");
    $payload = json_encode(["api_key" => $apiKey]);
    
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($httpCode !== 200) {
        throw new Exception("Erro ao autenticar: $response");
    }
    
    $data = json_decode($response, true);
    return $data['access_token'];
}

// 2. Função para Extrair DANFE
function extrairDanfe($baseUrl, $accessToken, $caminhoArquivo, $modeloIa = 'gemini') {
    $ch = curl_init("$baseUrl/danfe/extrair");
    
    $cFile = new CURLFile($caminhoArquivo, 'application/pdf', basename($caminhoArquivo));
    $postData = [
        'file' => $cFile,
        'modelo_ia' => $modeloIa
    ];
    
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $postData);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "Authorization: Bearer $accessToken"
    ]);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($httpCode !== 200) {
        throw new Exception("Erro na extração: $response");
    }
    
    return json_decode($response, true);
}

// Execução
try {
    $token = obterToken($baseUrl, $apiKey);
    $resultado = extrairDanfe($baseUrl, $token, 'exemplo_danfe.pdf', 'gemini');
    print_r($resultado);
} catch (Exception $e) {
    echo "❌ Erro: " . $e->getMessage();
}
```

---

## 5. Renovação de Token (Refresh Token)

Quando seu `access_token` expirar (após 60 minutos), você pode renová-lo usando o `refresh_token` sem reenviar a API Key:

- **Endpoint**: `POST /api/v1/auth/refresh`
- **Header**: `Content-Type: application/json`
- **Body**:
```json
{
  "refresh_token": "SEU_REFRESH_TOKEN_AQUI"
}
```

---

## 6. Códigos de Erro e Tratamento

| Código HTTP | Significado | Causa Comum |
| :--- | :--- | :--- |
| `401 Unauthorized` | Não autorizado | Token ausente, inválido ou expirado. API Key inválida. |
| `400 Bad Request` | Requisição inválida | Formato de arquivo não suportado (ex: .zip) ou modelo de IA inexistente. |
| `429 Too Many Requests` | Limite de requisições | Excedido o limite de 60 requisições/minuto. |
| `500 Internal Error` | Erro interno | Falha na resposta da API de IA ou indisponibilidade temporária. |

