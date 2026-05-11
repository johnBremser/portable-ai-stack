# API_CONTRACTS.md — Local AI Stack

> Contrato completo da API REST do backend FastAPI. Todos os endpoints, schemas e exemplos.

---

## 1. Informações Gerais

**Base URL:** `http://localhost:8500`

**Configuração:** Porta configurável via variável de ambiente `PORT` (default: 8500)

**CORS:** `allow_origins=["*"]` (todas as origens permitidas)

**Content-Type:** `application/json` (exceto `/chat/upload` que é `multipart/form-data`)

**Autenticação:** Nenhuma (uso local isolado)

---

## 2. Endpoints

### 2.1 Health Check

**Método:** `GET`

**Rota:** `/health`

**Descrição:** Verifica status da API e do Ollama. Retorna modelos disponíveis e sessões ativas.

**Request:**
```
GET /health
```

**Response (200 OK):**
```json
{
  "api": "online",
  "ollama": "online",
  "models": ["gemma4:e2b", "qwen3.5:4b"],
  "sessions_active": 3,
  "timestamp": "2026-04-15T10:30:00.000000",
  "api_version": "1.0.1",
  "pdf_raster": "pymupdf",
  "attachments_py": "/path/to/backend/attachments.py"
}
```

**Campos:**
- `api`: Status da API (`"online"` ou `"offline"`)
- `ollama`: Status do Ollama (`"online"` ou `"offline"`)
- `models`: Lista de nomes de modelos disponíveis
- `sessions_active`: Número de sessões ativas em memória
- `timestamp`: Timestamp ISO da resposta
- `api_version`: Versão da API
- `pdf_raster`: Engine de rasterização PDF (`"pymupdf"`)
- `attachments_py`: Caminho do módulo attachments (diagnóstico)

**Headers:**
- `Cache-Control: no-store, no-cache, must-revalidate`
- `Pragma: no-cache`

---

### 2.2 Stack Info

**Método:** `GET`

**Rota:** `/stack-info`

**Descrição:** Diagnóstico de versão e caminho do módulo attachments (evita confusão com cache ou processo antigo).

**Request:**
```
GET /stack-info
```

**Response (200 OK):**
```json
{
  "api_version": "1.0.1",
  "pdf_raster": "pymupdf",
  "attachments_py": "/path/to/backend/attachments.py",
  "cwd": "/path/to/backend"
}
```

**Headers:**
- `Cache-Control: no-store, no-cache, must-revalidate`
- `Pragma: no-cache`

---

### 2.3 List Models

**Método:** `GET`

**Rota:** `/models`

**Descrição:** Lista todos os modelos disponíveis no Ollama local.

**Request:**
```
GET /models
```

**Response (200 OK):**
```json
{
  "models": [
    {
      "name": "gemma4:e2b",
      "size_gb": 3.25,
      "modified": "2026-04-10T08:00:00.000000"
    },
    {
      "name": "qwen3.5:4b",
      "size_gb": 2.80,
      "modified": "2026-04-09T12:00:00.000000"
    }
  ]
}
```

**Error Response (503 Service Unavailable):**
```json
{
  "detail": "Ollama indisponível: [mensagem de erro]"
}
```

---

### 2.4 Chat (Streaming SSE)

**Método:** `POST`

**Rota:** `/chat`

**Descrição:** Envia uma mensagem e retorna a resposta em streaming via Server-Sent Events (SSE). Ideal para interfaces que exibem tokens em tempo real. Mantém histórico por session_id.

**Content-Type da Response:** `text/event-stream`

**Request Schema:**
```json
{
  "message": "<string, min_length=1>",
  "session_id": "<string, optional>",
  "model": "<string, default='gemma4:e2b'>",
  "system_prompt": "<string, optional>",
  "temperature": "<float, 0.0-2.0, default=0.7>",
  "max_tokens": "<int, 64-8192, default=2048>",
  "top_p": "<float, 0.0-1.0, default=0.9>",
  "top_k": "<int, 0-100000, default=40>",
  "think": "<bool, default=false>"
}
```

**Exemplo de Request:**
```json
{
  "message": "O que é um Large Language Model?",
  "model": "gemma4:e2b",
  "temperature": 0.7,
  "max_tokens": 2048
}
```

**Response (200 OK):** `text/event-stream`

**Event Types:**

| Type | Descrição | Schema |
|---|---|---|
| `start` | Primeiro evento; contém session_id | `{"session_id": "<UUID>", "type": "start"}` |
| `think` | Token de raciocínio interno (se `think=true`) | `{"type": "think", "token": "<string>"}` |
| `token` | Token de resposta | `{"type": "token", "token": "<string>"}` |
| `done` | Último evento; contém tokens_used | `{"type": "done", "session_id": "<UUID>", "tokens_used": <int>}` |
| `error` | Erro durante stream | `{"type": "error", "detail": "<string>"}` |

**Exemplo de Stream:**
```
data: {"session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "type": "start"}

data: {"type": "token", "token": "Um"}

data: {"type": "token", "token": " Large"}

data: {"type": "token", "token": " Language"}

data: {"type": "token", "token": " Model"}

data: {"type": "token", "token": " (LLM)"}

data: {"type": "token", "token": " é"}

data: {"type": "token", "token": " um"}

data: {"type": "token", "token": " modelo"}

data: {"type": "token", "token": " de"}

data: {"type": "token", "token": " linguagem."}

data: {"type": "done", "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "tokens_used": 128}
```

**Headers:**
- `Cache-Control: no-cache`
- `X-Accel-Buffering: no` (necessário para nginx/proxies)

**Notas:**
- Frontend deve acumular tokens para formar resposta completa
- Evento `think` só aparece se modelo suporta thinking e `think=true`
- Painel de thinking pode ser colapsável no frontend
- Em caso de erro, o stream envia `{"type": "error", "detail": "..."}`

---

### 2.5 Chat com Upload de Anexo (Streaming SSE)

**Método:** `POST`

**Rota:** `/chat/upload`

**Descrição:** Envia mensagem com um anexo (imagem, texto/código, PDF) e retorna a resposta em streaming via Server-Sent Events (SSE). Usa `multipart/form-data`.

**Content-Type:** `multipart/form-data`

**Content-Type da Response:** `text/event-stream`

**Form Fields:**

| Campo | Tipo | Obrigatório | Default | Descrição |
|---|---|---|---|---|
| `file` | File | Sim | — | Arquivo para anexar |
| `message` | string | Não | `""` | Mensagem do usuário |
| `session_id` | string | Não | `""` | ID da sessão (cria nova se vazio) |
| `model` | string | Não | `"gemma4:e2b"` | Modelo a usar |
| `system_prompt` | string | Não | `""` | Prompt de sistema |
| `temperature` | string | Não | `"0.7"` | Temperatura (0.0-2.0) |
| `max_tokens` | string | Não | `"2048"` | Máx tokens (64-8192) |
| `top_p` | string | Não | `"0.9"` | Top P (0.0-1.0) |
| `top_k` | string | Não | `"40"` | Top K (0-100000) |
| `think` | string | Não | `"false"` | Ativa thinking (`"true"`/`"false"`) |

**Exemplo de Request (curl):**
```bash
curl -X POST http://localhost:8500/chat/upload \
  -F "file=@documento.pdf" \
  -F "message=Analise este documento" \
  -F "model=gemma4:e2b" \
  -F "temperature=0.5"
```

**Response (200 OK):** `text/event-stream`

**Event Types:**

| Type | Descrição | Schema |
|---|---|---|
| `attachment_info` | Info do anexo processado (primeiro evento) | `{"type": "attachment_info", "mode": "<string>", "summary": "<string>", "history_tag": "<string>", "text_chars": <int|null>, "image_count": <int>, "extracted_non_ws": <int|null>}` |
| `start` | Primeiro evento após attachment_info; contém session_id | `{"session_id": "<UUID>", "type": "start"}` |
| `think` | Token de raciocínio interno (se `think=true`) | `{"type": "think", "token": "<string>"}` |
| `token` | Token de resposta | `{"type": "token", "token": "<string>"}` |
| `done` | Último evento; contém tokens_used | `{"type": "done", "session_id": "<UUID>", "tokens_used": <int>}` |
| `error` | Erro durante stream | `{"type": "error", "detail": "<string>"}` |

**Exemplo de Stream:**
```
data: {"type": "attachment_info", "mode": "pdf_text", "summary": "Texto extraído do PDF...", "history_tag": "pdf-texto", "text_chars": 15234, "image_count": 0, "extracted_non_ws": 12456}

data: {"session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "type": "start"}

data: {"type": "token", "token": "O"}

data: {"type": "token", "token": " documento"}

data: {"type": "token", "token": " contém"}

data: {"type": "token", "token": " dados"}

data: {"type": "token", "token": " sobre"}

data: {"type": "token", "token": " vendas."}

data: {"type": "done", "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "tokens_used": 256}
```

**Attachment Modes:**

| Mode | history_tag | Descrição |
|---|---|---|
| `pdf_text` | `pdf-texto` | PDF com texto extraível (>= 80 chars não-brancos) |
| `pdf_images` | `pdf-imagem` | PDF com pouco texto; páginas rasterizadas como PNG |
| `image` | `imagem` | Imagem convertida para PNG base64 |
| `text_file` | `texto` | Arquivo de texto/código lido como UTF-8 |

**Headers:**
- `Cache-Control: no-cache`
- `X-Accel-Buffering: no` (necessário para nginx/proxies)

**Notas:**
- Frontend deve acumular tokens para formar resposta completa
- Evento `think` só aparece se modelo suporta thinking e `think=true`
- Em caso de erro, o stream envia `{"type": "error", "detail": "..."}`

---

### 2.6 Get Session History

**Método:** `GET`

**Rota:** `/session/{session_id}`

**Descrição:** Retorna o histórico de mensagens de uma sessão.

**Request:**
```
GET /session/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response (200 OK):**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "messages": [
    {"role": "user", "content": "O que é IA?"},
    {"role": "assistant", "content": "Inteligência Artificial é..."},
    {"role": "user", "content": "E machine learning?"},
    {"role": "assistant", "content": "Machine Learning é..."}
  ],
  "total": 4
}
```

**Error Response (404 Not Found):**
```json
{
  "detail": "Sessão não encontrada."
}
```

---

### 2.7 Clear Session

**Método:** `DELETE`

**Rota:** `/session/{session_id}`

**Descrição:** Limpa o histórico de uma sessão (inicia nova conversa).

**Request:**
```
DELETE /session/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response (200 OK):**
```json
{
  "message": "Histórico limpo com sucesso.",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Error Response (404 Not Found):**
```json
{
  "detail": "Sessão não encontrada."
}
```

---

### 2.8 Clear All Sessions

**Método:** `DELETE`

**Rota:** `/sessions`

**Descrição:** Limpa todas as sessões ativas (uso administrativo).

**Request:**
```
DELETE /sessions
```

**Response (200 OK):**
```json
{
  "message": "3 sessão(ões) removida(s)."
}
```

---

## 3. Schemas Pydantic

### 3.1 ChatRequest

```python
class ChatRequest(BaseModel):
    message: str                                    # Required, min_length=1
    session_id: Optional[str] = None                # UUID ou None (cria nova)
    model: str = "gemma4:e2b"                       # Nome do modelo Ollama
    system_prompt: Optional[str] = None             # Prompt de sistema
    temperature: float = 0.7                        # 0.0 - 2.0
    max_tokens: int = 2048                          # 64 - 8192
    top_p: float = 0.9                              # 0.0 - 1.0
    top_k: int = 40                                 # 0 - 100000
    think: bool = False                             # Ativa thinking
```

### 3.2 ChatResponse (DEPRECATED — substituído por eventos SSE)

> **Nota:** Este schema não é mais usado como `response_model`. Os endpoints `/chat` e `/chat/upload` agora retornam streaming SSE (`text/event-stream`). O schema é mantido apenas como referência dos campos que eram retornados em JSON.

```python
class ChatResponse(BaseModel):
    session_id: str                                 # UUID da sessão
    response: str                                   # Resposta do modelo
    model: str                                      # Modelo utilizado
    tokens_used: Optional[int]                      # Tokens consumidos (ou None)
    timestamp: str                                  # Timestamp ISO
    attachment: Optional[AttachmentProcessInfo]     # Info do anexo (ou None)
```

**Equivalência com eventos SSE:**

| Campo ChatResponse | Evento SSE equivalente |
|---|---|
| `session_id` | `start.session_id` / `done.session_id` |
| `response` | Acumulação de todos os eventos `token` |
| `model` | Enviado no request (não há evento separado) |
| `tokens_used` | `done.tokens_used` |
| `timestamp` | Não enviado no stream (frontend pode gerar) |
| `attachment` | `attachment_info` (apenas em `/chat/upload`) |

### 3.3 AttachmentProcessInfo

```python
class AttachmentProcessInfo(BaseModel):
    mode: str                   # "pdf_text", "pdf_images", "image", "text_file"
    summary: str                # Descrição resumida do processamento
    history_tag: str            # Tag para histórico ("pdf-texto", "imagem", etc.)
    text_chars: Optional[int]   # Caracteres de texto extraído (ou None)
    image_count: int            # Número de imagens enviadas ao Ollama
    extracted_non_ws: Optional[int]  # PDF: chars não-brancos extraídos (ou None)
```

---

## 4. Error Handling

**Formato padrão de erros no streaming SSE:**
```json
{"type": "error", "detail": "<mensagem de erro>"}
```

Erros durante o stream são enviados como eventos SSE com `type: "error"`. O frontend deve tratar esse evento para exibir a mensagem de erro ao usuário.

**Validation Errors (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

**HTTP Status Codes:**

| Código | Significado | Quando ocorre |
|---|---|---|
| 200 | OK | Requisição bem-sucedida (stream SSE iniciado) |
| 404 | Not Found | Sessão não encontrada |
| 415 | Unsupported Media Type | Tipo de arquivo não suportado no upload |
| 422 | Unprocessable Entity | Validação de schema ou parâmetros |
| 500 | Internal Server Error | Erro interno não categorizado (enviado como evento `error` no stream) |
| 502 | Bad Gateway | Erro do Ollama (enviado como evento `error` no stream) |
| 503 | Service Unavailable | Ollama indisponível |
| 504 | Gateway Timeout | Timeout na resposta do modelo (enviado como evento `error` no stream) |

---

## 5. Exemplos de Uso

### 5.1 Chat Simples (curl)

```bash
curl -N -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "O que é um Large Language Model?",
    "model": "gemma4:e2b",
    "temperature": 0.7
  }'
```

> A flag `-N` (`--no-buffer`) desabilita buffering para ver os eventos SSE em tempo real.

### 5.2 Chat com Upload de PDF (curl)

```bash
curl -N -X POST http://localhost:8500/chat/upload \
  -F "file=@relatorio.pdf" \
  -F "message=Resuma este documento" \
  -F "model=gemma4:e2b"
```

> O stream começa com o evento `attachment_info` seguido dos eventos `token`.

### 5.3 Listar Modelos (curl)

```bash
curl http://localhost:8500/models
```

### 5.4 Health Check (curl)

```bash
curl http://localhost:8500/health
```

### 5.5 Limpar Sessão (curl)

```bash
curl -X DELETE http://localhost:8500/session/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 5.6 Chat Simples (limitando output para teste)

Para testes rápidos, é possível limitar o output com `head -c`:

```bash
curl -s -N -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explique IA em uma frase", "model": "gemma4:e2b"}' \
  | head -c 2000
```

> Isso exibe os primeiros 2000 bytes do stream SSE, suficiente para verificar o formato dos eventos.

---

## 6. Documentação Interativa (Swagger)

A API expõe documentação automática via Swagger UI:

**URL:** `http://localhost:8500/docs`

**Alternativa (ReDoc):** `http://localhost:8500/redoc`

---

*Documento alinhado com PROJECT_SPEC.md. Última atualização: abril 2026.*
