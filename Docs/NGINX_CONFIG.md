# Guia de Configuração do Nginx com Subrotas (Reverse Proxy)

Este documento descreve como configurar o Nginx para redirecionar tráfego do domínio público **`b2bi-apps.luftfarma.com.br`** sob a subrota desejada (ex: `/api-ia` ou `/danfe-api`) para a aplicação Python/FastAPI (`http://172.16.200.80:9008`).

---

## 1. Funcionamento do `ROOT_PATH` na API

A API foi configurada para aceitar a variável de ambiente `ROOT_PATH` no arquivo `.env`.

Exemplo no `.env`:
```env
HOST=0.0.0.0
PORT=9008
DEBUG=False
ROOT_PATH=/api-ia
```

Quando o `ROOT_PATH=/api-ia` está ativo:
- A documentação Swagger UI estará disponível em: `http://b2bi-apps.luftfarma.com.br/api-ia/docs`
- O Healthcheck estará em: `http://b2bi-apps.luftfarma.com.br/api-ia/`
- Os endpoints de autenticação estarão em: `http://b2bi-apps.luftfarma.com.br/api-ia/api/v1/auth/token`
- Os endpoints de extração estarão em: `http://b2bi-apps.luftfarma.com.br/api-ia/api/v1/danfe/extrair`

---

## 2. Exemplo de Configuração no Nginx

No arquivo de configuração do seu site no Nginx (ex: `/etc/nginx/sites-available/b2bi-apps` ou `/etc/nginx/conf.d/b2bi-apps.conf`):

```nginx
server {
    listen 80;
    server_name b2bi-apps.luftfarma.com.br;

    # Limite máximo de upload para arquivos de DANFE (PDFs / Imagens)
    client_max_body_size 25M;

    # -------------------------------------------------------------
    # Subrota para a API de IA DANFE Extractor
    # -------------------------------------------------------------
    location /api-ia/ {
        proxy_pass http://172.16.200.80:9008/;
        
        # Headers essenciais para repassar IPs e protocolo original
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Prefix /api-ia;

        # Timeouts ajustados para processamento da IA (quando arquivos grandes demoram mais)
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
    }

    # -------------------------------------------------------------
    # Outras aplicações já existentes no servidor...
    # -------------------------------------------------------------
    # location /outra-aplicacao/ {
    #     proxy_pass http://127.0.0.1:8080/;
    # }
}
```

---

## 3. Validação e Recarregamento do Nginx

Após salvar a configuração no Nginx, execute os comandos abaixo no servidor Nginx para testar e aplicar:

```bash
# 1. Testar a sintaxe do arquivo de configuração Nginx
sudo nginx -t

# 2. Recarregar o serviço do Nginx caso o teste passe sem erros
sudo nginx -s reload
```

---

## 4. Testando a API via Nginx

### Healthcheck
```bash
curl -X GET "http://b2bi-apps.luftfarma.com.br/api-ia/"
```

Retorno esperado:
```json
{
  "status": "online",
  "aplicacao": "API de Extracao de DANFE",
  "versao": "1.1.0",
  "subrota": "/api-ia",
  "documentacao": "/api-ia/docs",
  "autenticacao": "JWT via /api-ia/api/v1/auth/token"
}
```

### Documentação Interativa (Swagger)
Acesse via navegador:
`http://b2bi-apps.luftfarma.com.br/api-ia/docs`
