# ARCHITECTURE.md — Local AI Stack

> Detalhamento da arquitetura do sistema, camadas, componentes e fluxos de dados.

---

## 1. Visão Geral da Arquitetura

O Local AI Stack segue uma **arquitetura em camadas (layered) com separação frontend/backend**, comunicando-se via HTTP REST. Não é monolito puro nem microserviços — é uma **arquitetura de 3 camadas desacopladas**:

```
[Camada de Apresentação]  →  [Camada de Aplicação]  →  [Camada de Inferência]
  Frontend (Browser)            Backend (FastAPI)         Ollama (LLM)
  Porta 8501/8502               Porta 8500                Porta 11434
```

**Características arquiteturais:**
- Separação completa de concerns: frontend não acessa Ollama diretamente
- API RESTful com CORS habilitado (`allow_origins=["*"]`)
- Sessões em memória (dict Python) — sem banco de dados persistido
- Streaming via Server-Sent Events (SSE) como modo padrão em `/chat` e `/chat/upload`
- Upload multipart para anexos no endpoint `/chat/upload`
- Stateless entre reinícios: sessões são voláteis (em memória)

---

## 2. Camadas e Responsabilidades

### 2.1 Camada de Apresentação (Frontend)

**Tecnologias:** Streamlit (principal) ou HTML5/JS (alternativo)

**Componentes:**

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| **Streamlit UI** | `frontend/app.py` | Interface de chat reativa com tema customizado (vinho/preto), sidebar com controles, métricas de sessão, diálogo de arquivos via tkinter |
| **HTML5 Server** | `frontend/app_web.py` | Servidor HTTP standalone (stdlib Python) para servir frontend HTML5 puro |
| **HTML5 UI** | `frontend/web/index.html` | Página HTML5 alternativa (sem dependência de Streamlit) |
| **JavaScript Logic** | `frontend/web/app.js` | Lógica de chat, consumo de SSE (ReadableStream), sanitização (DOMPurify), renderização Markdown (marked) |
| **CSS Styles** | `frontend/web/styles.css` | Design system dark com vinho (#8b1a1a), responsivo (sidebar drawer em mobile) |

**Portas:**
- Streamlit: **8501**
- HTML5: **8502** (configurável via `WEB_PORT`)

**Responsabilidades da camada:**
- Renderizar interface de chat
- Capturar input do usuário
- Exibir histórico de mensagens
- Gerenciar upload de arquivos
- Comunicar com backend via HTTP REST
- Exibir métricas de sessão (mensagens, tokens)

### 2.2 Camada de Aplicação (Backend)

**Tecnologias:** FastAPI + Uvicorn + httpx + Pydantic

**Componentes:**

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| **API REST** | `backend/api.py` | Todos os endpoints, gerenciamento de sessões, roteamento para Ollama, validação de schemas |
| **Processamento de Anexos** | `backend/attachments.py` | Classificação e processamento de arquivos (PDF, imagem, texto), extração de texto, rasterização, redimensionamento |

**Porta:** **8500** (configurável via env `PORT`)

**Responsabilidades da camada:**
- Receber requisições HTTP do frontend
- Gerenciar sessões e histórico (dict em memória)
- Validar schemas de entrada (Pydantic)
- Processar arquivos anexados
- Montar payloads para Ollama (sempre com `stream: true`)
- Encaminhar respostas via SSE (tokens streaming)
- Health check e diagnóstico

### 2.3 Camada de Inferência (Ollama)

**Tecnologia:** Ollama (serviço local)

**Porta:** **11434**

**Responsabilidades:**
- Servir modelos LLM locais
- Processar requests `/api/chat` (com `stream: true`)
- Retornar respostas via streaming (linhas JSON com tokens)
- Suportar multimodalidade (array `images` para base64)
- Suportar thinking interno (parâmetro `think`)

**Modelos suportados:**
- Padrão: `gemma4:e2b`
- Alternativos: qualquer modelo instalado via `ollama pull`

---

## 3. Diagrama de Fluxo de Dados

### 3.1 Fluxo de Requisição de Chat (sem anexo)

```
┌──────────┐    POST /chat (SSE)        ┌──────────────┐    POST /api/chat     ┌─────────┐
│          │ ───────────────────────→   │              │ ───────────────────→ │         │
│  Browser │                            │   FastAPI    │                       │  Ollama │
│          │ ←────────────────────────  │              │ ←─────────────────── │         │
└──────────┘    SSE (text/event-stream) └──────────────┘    SSE streaming     └─────────┘
                      │                        │
                      │                        │ Salva (user, assistant)
                      │                        │ em sessions[session_id]
                      ▼                        ▼
               Exibe balão            Histórico atualizado
               do assistente          (máx 20 turnos)
               via tokens SSE
```

### 3.2 Fluxo de Requisição com Anexo

```
┌──────────┐   POST /chat/upload        ┌──────────────┐    process_attachment   ┌──────────────┐
│          │ ───────────────────────→   │              │ ──────────────────────→ │              │
│  Browser │  (multipart/form-data)     │   FastAPI    │                          │ attachments  │
│          │                            │              │ ←────────────────────── │  .py         │
│          │ ←────────────────────────  │              │    SSE streaming        │              │
└──────────┘    SSE (text/event-stream) │              │                          └──────────────┘
                      │                 │              │
                      │                 │ Monta messages com images[] (base64)
                      │                 │ POST /api/chat (stream: True)
                      │                 ▼
                      │           ┌─────────┐
                      │           │  Ollama │
                      │           └────┬────┘
                      │                │
                      │                │ SSE streaming
                      ▼                ▼
               Exibe balão       Salva histórico
               do assistente     com tag de anexo
               via tokens SSE
```

### 3.3 Fluxo de Inicialização (script completo)

```
┌─────────────────────────────────────────────────────────────┐
│                    start_all.sh / .bat                       │
├─────────────────────────────────────────────────────────────┤
│  1. Verifica Ollama instalado                                │
│  2. Inicia ollama serve (background, se necessário)          │
│  3. Baixa modelo gemma4:e2b (se não existir)                 │
│  4. Cria venv backend → instala deps → sobe uvicorn          │
│  5. Health check no backend (aguarda porta 8500)             │
│  6. Cria venv frontend → instala deps → sobe streamlit       │
│  7. Abre navegador em http://localhost:8501                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Integração entre Componentes

### 4.1 Backend → Ollama

**Protocolo:** HTTP REST (httpx)

**Endpoints utilizados:**
- `GET /api/tags` — Lista modelos disponíveis
- `POST /api/chat` — Envia mensagem e recebe resposta via streaming

**Payload de request:**
```json
{
  "model": "gemma4:e2b",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "...", "images": ["base64..."]}
  ],
  "stream": true,
  "think": false,
  "options": {
    "temperature": 0.7,
    "num_predict": 2048,
    "top_p": 0.9,
    "top_k": 40
  }
}
```

**Resposta (streaming):** O Ollama retorna linhas JSON individuais, cada uma contendo um token (ou trecho de thinking). O backend repassa esses tokens como eventos SSE ao frontend. Cada linha tem o formato:
```json
{"message": {"role": "assistant", "content": "...", "thinking": "..."}, "done": false, "eval_count": 128}
```
Quando `"done": true`, o campo `eval_count` indica o total de tokens gerados.

### 4.2 Frontend → Backend

**Protocolo:** HTTP REST (httpx no Streamlit, fetch no HTML5)

**Endpoints utilizados:**
- `GET /health` — Verifica status
- `GET /models` — Lista modelos
- `POST /chat` — Chat com streaming SSE
- `POST /chat/upload` — Chat com anexo (multipart/form-data) com streaming SSE
- `GET /session/{id}` — Histórico
- `DELETE /session/{id}` — Limpa sessão
- `DELETE /sessions` — Limpa todas as sessões

**Nota sobre SSE:** Tanto `/chat` quanto `/chat/upload` retornam `text/event-stream`. O frontend HTML5 consome os tokens em tempo real via `ReadableStream`. O frontend Streamlit usa httpx síncrono e espera a resposta completa (o backend acumula os tokens internamente antes de retornar o JSON final).

### 4.3 CORS

**Configuração:** `allow_origins=["*"]`

**Motivo:** Frontend e backend rodam em portas diferentes, exigindo CORS para comunicação cross-origin.

**Risco:** Seguro apenas em rede local isolada. Não expor backend à internet.

---

## 5. Regras de Dependência

### 5.1 Dependências do Backend (`backend/requirements.txt`)

```
fastapi==0.115.6
uvicorn[standard]==0.32.1
httpx==0.28.1
pydantic==2.10.4
pypdf==5.1.0
pymupdf==1.25.3
Pillow==11.0.0
python-multipart==0.0.20
```

### 5.2 Dependências do Frontend (`frontend/requirements.txt`)

```
streamlit==1.41.1
httpx==0.28.1
```

### 5.3 Dependências de Frontend HTML5 (CDN)

- **Google Fonts (Inter):** `fonts.googleapis.com`
- **marked:** `cdn.jsdelivr.net/npm/marked@~12.0.2`
- **DOMPurify:** `cdn.jsdelivr.net/npm/dompurify@~3.2.2`

### 5.4 Dependência Externa Crítica

**Ollama:** Serviço local obrigatório na porta 11434. Sem Ollama, backend opera mas não processa requisições de chat.

---

## 6. Padrões Arquiteturais

### 6.1 Gerenciamento de Sessões

**Estrutura:** `sessions: dict[str, list[dict]]` (memória)

**Chave:** UUID v4 (string)

**Valor:** Lista de mensagens (role + content)

**Limite:** 20 turnos por sessão (`MAX_HISTORY = 20`)

**Ciclo de vida:**
- Criação: automática no primeiro request (`get_or_create_session`)
- Atualização: append de par (user, assistant) após resposta
- Limpeza: individual (`DELETE /session/{id}`) ou global (`DELETE /sessions`)
- Expiração: inexistente; sessão persiste até reinício do backend

### 6.2 Streaming via SSE

**Endpoints:** `POST /chat` e `POST /chat/upload`

**Implementação:**
- O backend SEMPRE chama Ollama com `stream: True` (função `_build_ollama_payload`)
- A função `_stream_ollama_events` faz o stream dos tokens via `httpx.AsyncClient.stream` e yield eventos SSE
- Cada evento é uma linha JSON: `{"type": "token", "token": "..."}`
- Eventos especiais: `start` (session_id), `think` (raciocínio interno), `done` (fim + tokens_used), `error`
- Frontend HTML5 usa `ReadableStream` + `TextDecoder` para consumir tokens em tempo real
- Frontend Streamlit usa chamada síncrona (não faz streaming; aguarda resposta completa)
- Não há mais endpoint `/chat/stream` — SSE é o modo padrão e único

### 6.3 Processamento de Anexos

**Classificação:**
1. Detecta tipo por extensão + MIME type
2. PDF → `_process_pdf()`
3. Imagem → `_process_image()`
4. Texto → `_process_text_file()`
5. Desconhecido → `AttachmentError`

**PDF — Decisão texto vs imagem:**
- Extrai texto com pypdf + PyMuPDF (melhor resultado)
- Conta caracteres não-brancos
- Se >= 80 chars → retorna texto inline
- Se < 80 chars → rasteriza páginas como PNG (máx 5)

**Retorno:** `AttachmentOutcome(history_tag, extra_content, images, pdf_extracted_non_ws)`

---

## 7. Pontos de Acoplamento

### 7.1 Acoplamento Forte
- `api.py` ↔ `attachments.py`: imports diretos, compartilhamento de `AttachmentOutcome` e `AttachmentError`
- Frontend ↔ Backend: dependência de schema de request/response (quebrar API quebra frontend)

### 7.2 Acoplamento Fraco
- Backend ↔ Ollama: comunicação via HTTP REST; trocar Ollama por outro serviço requer apenas mudar URL
- Frontend Streamlit ↔ Frontend HTML5: independentes; ambos consomem mesma API

### 7.3 Riscos de Acoplamento
- Alterar schema de `ChatRequest` ou `ChatResponse` requer atualização em ambos os frontends
- Mudar porta padrão do backend requer atualização em ambos os frontends e scripts

---

## 8. Invariantes Arquiteturais

**Estes invariantes NÃO devem ser quebrados:**

1. Frontend nunca acessa Ollama diretamente
2. Backend gerencia sessões e histórico
3. Anexos são processados no backend (nunca no frontend)
4. Histórico é limitado (MAX_HISTORY = 20)
5. CORS permite todas as origens (uso local isolado)
6. Sessões são voláteis (sem persistência em disco)
7. Ollama é dependência externa obrigatória

---

*Documento alinhado com PROJECT_SPEC.md. Última atualização: abril 2026.*
