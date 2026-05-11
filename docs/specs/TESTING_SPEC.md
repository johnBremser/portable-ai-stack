# TESTING_SPEC.md — Local AI Stack

> Estratégia de testes, mapeamento de funcionalidades para casos de teste e exemplos de validação.

---

## 1. Estratégia de Testes

O Local AI Stack atualmente utiliza **testes manuais via curl** como estratégia principal. Não há framework de testes automatizados (pytest, unittest) implementado.

**Abordagem atual:**
- Script `backend/test_api.sh` testa endpoints via curl
- Validação visual via interface Streamlit/HTML5
- Health check como diagnóstico rápido

**Abordagem recomendada:**
- Implementar testes unitários com pytest para backend
- Implementar testes de integração com mock do Ollama
- Manter testes manuais via curl para validação end-to-end

---

## 2. Tipos de Teste

### 2.1 Testes Unitários (Recomendado)

**Escopo:** Funções individuais do backend

**Ferramenta:** pytest

**Áreas prioritárias:**

| Módulo | Funções para Testar | Prioridade |
|---|---|---|
| `attachments.py` | `process_attachment()`, `compose_user_message()` | **Alta** |
| `attachments.py` | `_extract_pdf_text()`, `_process_image()`, `_process_text_file()` | **Alta** |
| `attachments.py` | `_is_pdf()`, `_is_probably_image()`, `_is_probably_text()` | Média |
| `api.py` | `get_or_create_session()`, `build_messages()`, `update_history()` | **Alta** |
| `api.py` | `_ollama_assistant_reply()` | Média |
| `api.py` | `_parse_upload_form()` | Média |
| `api.py` | `_attachment_process_info()` | Baixa |

### 2.2 Testes de Integração (Recomendado)

**Escopo:** Endpoints da API com mock do Ollama

**Ferramenta:** pytest + httpx.TestClient + respx (mock de HTTP)

**Endpoints para testar:**

| Endpoint | Método | Teste Principal |
|---|---|---|
| `/health` | GET | Retorna status online/offline |
| `/models` | GET | Lista modelos do Ollama |
| `/chat` | POST | Stream de tokens via SSE (default) |
| `/chat/upload` | POST | Processa anexo e retorna stream via SSE |
| `/session/{id}` | GET | Retorna histórico |
| `/session/{id}` | DELETE | Limpa histórico |
| `/sessions` | DELETE | Limpa todas as sessões |

### 2.3 Testes End-to-End (Manual)

**Escopo:** Fluxo completo do usuário

**Ferramenta:** `test_api.sh` + interface web

**Fluxos para testar:**
1. Chat sem anexo (SSE streaming)
2. Chat com anexo (SSE streaming via /chat/upload)
3. Chat com anexo (PDF, imagem, texto)
4. Histórico de sessão
5. Limpar sessão
6. Health check

### 2.4 Testes de Frontend (Manual)

**Escopo:** Interface de usuário

**Ferramenta:** Navegador

**Casos para testar:**
1. Enviar mensagem e ver resposta
2. Anexar arquivo e ver processamento
3. Ver histórico após múltiplas mensagens
4. Limpar conversa e recomeçar
5. Mudar modelo e parâmetros
6. Streaming em tempo real (HTML5)
7. Responsividade em mobile

---

## 3. Mapeamento Funcionalidade → Testes

### 3.1 Chat sem Anexo

| # | Funcionalidade | Teste | Tipo |
|---|---|---|---|
| F1 | Criar nova sessão | POST /chat sem session_id → retorna UUID | Integração |
| F2 | Reutilizar sessão | POST /chat com session_id → mantém histórico | Integração |
| F3 | Histórico limitado a 20 turnos | Enviar 25 mensagens → histórico tem 40 entries (20 user + 20 assistant) | Integração |
| F4 | Parâmetros do modelo | Variar temperature, top_p, top_k → resposta muda | Manual |
| F5 | System prompt | Enviar system_prompt → modelo segue instruções | Manual |
| F6 | Thinking | Enviar think=true com modelo compatível → painel de thinking aparece | Manual |

### 3.2 Chat com Anexo

| # | Funcionalidade | Teste | Tipo |
|---|---|---|---|
| F7 | Upload de PDF com texto | PDF com texto extraível → mode="pdf_text" | Integração |
| F8 | Upload de PDF escaneado | PDF sem texto → mode="pdf_images", image_count > 0 | Integração |
| F9 | Upload de imagem | JPG/PNG → mode="image", image_count=1 | Integração |
| F10 | Upload de texto | .txt/.csv/.py → mode="text_file" | Integração |
| F11 | Arquivo grande (>15MB) | Upload → HTTP 415 ou 422 | Integração |
| F12 | Arquivo vazio | Upload → HTTP 415 | Integração |
| F13 | Tipo não suportado | .exe/.zip → HTTP 415 | Integração |
| F14 | Truncamento de texto | Arquivo > 80.000 chars → truncado com aviso | Unitário |

### 3.3 Streaming (SSE — default em /chat e /chat/upload)

| # | Funcionalidade | Teste | Tipo |
|---|---|---|---|
| F15 | Stream de tokens via SSE | POST /chat → eventos SSE com tokens | Integração |
| F16 | Session ID no start | Primeiro evento tem session_id | Integração |
| F17 | Thinking no stream | think=true → eventos "think" antes de "token" | Integração |
| F18 | Evento done | Último evento tem tokens_used | Integração |
| F19 | Frontend HTML5 renderiza | Tokens aparecem em tempo real no browser | Manual |
| F20 | SSE Content-Type | Response header `Content-Type: text/event-stream` | Integração |

### 3.4 Gerenciamento de Sessões

| # | Funcionalidade | Teste | Tipo |
|---|---|---|---|
| F20 | Get session history | GET /session/{id} → retorna messages | Integração |
| F21 | Clear session | DELETE /session/{id} → histórico vazio | Integração |
| F22 | Clear all sessions | DELETE /sessions → todas as sessões removidas | Integração |
| F23 | Session não encontrada | GET/DELETE /session/{id} inexistente → HTTP 404 | Integração |

### 3.5 Health Check e Diagnóstico

| # | Funcionalidade | Teste | Tipo |
|---|---|---|---|
| F24 | Health check online | GET /health → api="online", ollama="online" | Integração |
| F25 | Health check Ollama offline | Ollama parado → ollama="offline" | Integração |
| F26 | Stack info | GET /stack-info → retorna api_version, attachments_py | Integração |
| F27 | List models | GET /models → lista modelos com size_gb | Integração |

---

## 4. Exemplos de Casos de Teste

### 4.1 Testes Unitários (Exemplos pytest)

#### Test: `process_attachment` com PDF válido

```python
def test_process_attachment_pdf_com_texto():
    """PDF com texto extraível deve retornar mode pdf-texto."""
    from backend.attachments import process_attachment
    
    # PDF simples com texto
    pdf_content = b"%PDF-1.4\n... [PDF válido com texto] ..."
    
    outcome = process_attachment("documento.pdf", "application/pdf", pdf_content)
    
    assert outcome.history_tag == "pdf-texto"
    assert len(outcome.images) == 0
    assert "documento.pdf" in outcome.extra_content
```

#### Test: `process_attachment` com imagem

```python
def test_process_attachment_imagem():
    """Imagem válida deve retornar mode imagem com base64."""
    from backend.attachments import process_attachment
    
    # Imagem PNG simples (1x1 pixel)
    png_data = b"\x89PNG\r\n\x1a\n..."  # Header PNG mínimo
    
    outcome = process_attachment("foto.png", "image/png", png_data)
    
    assert outcome.history_tag == "imagem"
    assert len(outcome.images) == 1
    assert isinstance(outcome.images[0], str)  # base64
    assert outcome.extra_content == ""
```

#### Test: `process_attachment` com arquivo grande

```python
def test_process_attachment_arquivo_grande():
    """Arquivo > 15MB deve levantar AttachmentError."""
    from backend.attachments import process_attachment, AttachmentError
    import pytest
    
    data = b"x" * (16 * 1024 * 1024)  # 16 MB
    
    with pytest.raises(AttachmentError, match="excede o limite"):
        process_attachment("grande.txt", "text/plain", data)
```

#### Test: `get_or_create_session`

```python
def test_get_or_create_session_nova():
    """Session_id None deve criar novo UUID."""
    from backend.api import get_or_create_session, sessions
    
    session_id = get_or_create_session(None)
    
    assert session_id is not None
    assert session_id in sessions
    assert len(sessions[session_id]) == 0
```

#### Test: `build_messages` com histórico

```python
def test_build_messages_com_historico():
    """Deve incluir histórico limitado a MAX_HISTORY turnos."""
    from backend.api import build_messages, sessions
    
    # Criar sessão com histórico
    sid = "test-session"
    sessions[sid] = [
        {"role": "user", "content": "msg 1"},
        {"role": "assistant", "content": "resp 1"},
        # ... adicionar 25 turnos
    ]
    
    messages = build_messages(sid, "nova mensagem", None)
    
    # Deve incluir system (se houver), histórico limitado, e nova mensagem
    assert len(messages) <= 2 + 20 + 1  # system + MAX_HISTORY + nova
    assert messages[-1]["content"] == "nova mensagem"
```

### 4.2 Testes de Integração (Exemplos pytest + httpx.TestClient)

#### Test: Health Check

```python
import pytest
from httpx import AsyncClient, ASGITransport
from backend.api import app

@pytest.mark.asyncio
async def test_health_check():
    """Health check deve retornar api online."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["api"] == "online"
    assert "ollama" in data
    assert "models" in data
```

#### Test: Chat SSE streaming

```python
import pytest
from httpx import AsyncClient, ASGITransport
from backend.api import app
import respx

def parse_sse_events(response_text):
    """Parse SSE events from response body."""
    events = []
    current_event = {}
    for line in response_text.splitlines():
        if line.startswith("event:"):
            current_event["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_event["data"] = line[len("data:"):].strip()
        elif line == "" and current_event:
            events.append(current_event)
            current_event = {}
    if current_event:
        events.append(current_event)
    return events

@pytest.mark.asyncio
async def test_chat_sse_streaming():
    """POST /chat deve retornar SSE stream com eventos de token."""
    with respx.mock:
        respx.post("http://localhost:11434/api/chat").respond(
            json={"message": {"content": "Olá!"}, "done": True, "eval_count": 10}
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/chat", json={
                "message": "Olá",
                "model": "gemma4:e2b"
            })

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = parse_sse_events(response.text)
        assert len(events) > 0

        # Verificar eventos de token
        token_events = [e for e in events if e.get("event") == "token"]
        assert len(token_events) > 0

        # Verificar evento done no final
        done_events = [e for e in events if e.get("event") == "done"]
        assert len(done_events) == 1
```

#### Test: Chat upload SSE streaming

```python
@pytest.mark.asyncio
async def test_chat_upload_sse_streaming():
    """POST /chat/upload deve retornar SSE stream com tokens."""
    import respx
    import io

    with respx.mock:
        respx.post("http://localhost:11434/api/chat").respond(
            json={"message": {"content": "Analise completa."}, "done": True, "eval_count": 50}
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat/upload",
                data={"message": "Analise este arquivo", "model": "gemma4:e2b"},
                files={"file": ("teste.txt", io.BytesIO(b"conteúdo do arquivo"), "text/plain")}
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = parse_sse_events(response.text)
        assert len(events) > 0

        # Deve ter pelo menos um evento token e um evento done
        token_events = [e for e in events if e.get("event") == "token"]
        done_events = [e for e in events if e.get("event") == "done"]
        assert len(token_events) > 0
        assert len(done_events) == 1
```

### 4.3 Testes Manuais via curl

> **Nota:** Todos os endpoints de chat (`/chat` e `/chat/upload`) retornam `text/event-stream`.
> Use `-N` (no-buffer) para ver tokens em tempo real. Para limitar output em testes,
> use `head -c N` ou redirecione para arquivo.

#### Test: Health Check

```bash
curl -s http://localhost:8500/health | python3 -m json.tool
```

**Resultado esperado:**
```json
{
  "api": "online",
  "ollama": "online",
  "models": ["gemma4:e2b"],
  "sessions_active": 0
}
```

#### Test: Chat SSE streaming

```bash
# Streaming em tempo real (no-buffer)
curl -N -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "O que é IA?", "model": "gemma4:e2b"}'
```

**Resultado esperado:** Eventos SSE no formato:
```
event: start
data: {"session_id": "...", "model": "gemma4:e2b"}

event: token
data: {"content": "Olá"}

event: token
data: {"content": "!"}

event: done
data: {"tokens_used": 15, "total_duration_ms": 3200}
```

Para limitar output (útil em scripts):
```bash
curl -N -s -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "O que é IA?", "model": "gemma4:e2b"}' | head -c 500
```

#### Test: Chat com Histórico (SSE)

```bash
# Primeira mensagem — salvar session_id
curl -N -s -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "O que é IA?", "model": "gemma4:e2b"}' > /tmp/resp1.txt

SESSION_ID=$(grep -o '"session_id": *"[^"]*"' /tmp/resp1.txt | head -1 | cut -d'"' -f4)

# Segunda mensagem (mesma sessão)
curl -N -s -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"E machine learning?\", \"session_id\": \"$SESSION_ID\", \"model\": \"gemma4:e2b"}"

# Verificar histórico (endpoint GET retorna JSON, não SSE)
curl -s http://localhost:8500/session/$SESSION_ID | python3 -m json.tool
```

**Resultado esperado:** Histórico com 4 entries (2 user + 2 assistant)

#### Test: Upload com SSE

```bash
curl -N -s -X POST http://localhost:8500/chat/upload \
  -F "message=Analise este arquivo" \
  -F "file=@teste.txt" \
  -F "model=gemma4:e2b" | head -c 300
```

---

## 5. Testes de Frontend

### 5.1 Streamlit (`frontend/app.py`)

| # | Teste | Como Validar |
|---|---|---|
| FE1 | Interface carrega | Acessar http://localhost:8501 |
| FE2 | Backend status badge | Verificar "Ollama online" na sidebar |
| FE3 | Enviar mensagem | Digitar e ver resposta no chat |
| FE4 | Anexar arquivo | Clicar 📎, selecionar arquivo, enviar |
| FE5 | Métricas atualizam | Contador de mensagens/tokens aumenta |
| FE6 | Limpar conversa | Botão 🗑️ limpa histórico |
| FE7 | Mudar parâmetros | Sliders na sidebar afetam resposta |
| FE8 | Responsividade | Redimensionar janela |

### 5.2 HTML5 (`frontend/web/`)

| # | Teste | Como Validar |
|---|---|---|
| FE9 | Interface carrega | Acessar http://localhost:8502 |
| FE10 | Streaming funciona | Tokens aparecem em tempo real |
| FE11 | Thinking panel colapsável | think=true mostra painel clicável |
| FE12 | Markdown renderiza | Respostas com **bold**, `code`, listas |
| FE13 | Sidebar responsiva | Drawer em telas < 860px |
| FE14 | Auto-resize textarea | Input cresce com texto |
| FE15 | Upload de arquivo | Input file + hint de arquivo selecionado |

---

## 6. Matriz de Cobertura

| Funcionalidade | Teste Unitário | Teste Integração | Teste Manual |
|---|---|---|---|
| Chat SSE (sem anexo) | ❌ | ✅ (POST /chat → SSE) | ✅ |
| Chat SSE (com upload) | ✅ (process_attachment) | ✅ (POST /chat/upload → SSE) | ✅ |
| Gerenciamento de sessões | ✅ (get_or_create_session) | ✅ (GET/DELETE /session) | ✅ |
| Health check | ❌ | ✅ (GET /health) | ✅ |
| List models | ❌ | ✅ (GET /models) | ✅ |
| Processamento PDF | ✅ (_extract_pdf_text) | ❌ | ✅ |
| Processamento imagem | ✅ (_process_image) | ❌ | ✅ |
| Processamento texto | ✅ (_process_text_file) | ❌ | ✅ |
| Frontend Streamlit | ❌ | ❌ | ✅ |
| Frontend HTML5 (SSE) | ❌ | ❌ | ✅ |

**Notas:**
- `/chat/stream` foi removido — streaming é o comportamento default de `/chat`
- `/chat` e `/chat/upload` ambos retornam `Content-Type: text/event-stream`

**Legenda:** ✅ = Existe ou é viável | ❌ = Não implementado

---

## 7. Recomendações para Implementação de Testes Automatizados

### 7.1 Framework Sugerido

```
pytest
pytest-asyncio
httpx (TestClient)
respx (mock de HTTP para Ollama)
```

### 7.2 Estrutura de Testes Sugerida

```
backend/
├── tests/
│   ├── test_api.py           # Testes dos endpoints
│   ├── test_attachments.py   # Testes de processamento de arquivos
│   ├── test_session.py       # Testes de gerenciamento de sessões
│   └── conftest.py           # Fixtures comuns
```

### 7.3 Fixtures Necessárias

```python
# conftest.py

import pytest
from httpx import AsyncClient, ASGITransport
from backend.api import app, sessions
import respx

@pytest.fixture
async def client():
    """Cliente HTTP para testar a API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
def mock_ollama():
    """Mock do Ollama para requests /api/chat."""
    with respx.mock:
        respx.post("http://localhost:11434/api/chat").respond(
            json={"message": {"content": "Resposta mockada."}, "done": True, "eval_count": 10}
        )
        yield

@pytest.fixture(autouse=True)
def clean_sessions():
    """Limpar sessões entre testes."""
    sessions.clear()
    yield
```

### 7.4 Comando de Execução

```bash
cd backend
pytest tests/ -v
```

---

## 8. Testes de Regressão

**Sempre testar após mudanças:**

1. **Health check** — API e Ollama operacionais
2. **Chat SSE básico** — Mensagem simples retorna stream SSE com tokens
3. **Upload de PDF via SSE** — PDF com texto e PDF escaneado
4. **SSE Content-Type** — Response headers incluem `text/event-stream`
5. **Histórico** — Sessão mantém contexto entre mensagens

---

## 9. Testes de Performance (Opcional)

**Métricas para monitorar:**

| Métrica | Como Medir | Valor Esperado |
|---|---|---|
| Latência SSE /chat | `time curl -N POST /chat` | < 30s (depende do modelo) |
| Tempo até primeiro token | `curl -N` + timestamp | < 5s |
| Throughput | Requisições simultâneas | 1-2 (single-thread Ollama) |
| Uso de memória | `ps aux | grep python` | < 2 GB (backend + Ollama) |
| Tamanho de sessão | 20 turnos em memória | < 100 KB |

---

*Documento alinhado com PROJECT_SPEC.md. Última atualização: abril 2026.*
