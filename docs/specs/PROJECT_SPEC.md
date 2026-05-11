# PROJECT_SPEC.md — Local AI Stack

> **Fonte única de verdade** para o projeto Local AI Stack. Todos os outros documentos e decisões devem alinhar-se com esta especificação.

---

## 1. Propósito do Sistema

O **Local AI Stack** é uma aplicação de chat com Modelos de Linguagem (LLMs) que roda **100% na máquina local**, sem dependência de serviços cloud. Permite interação conversacional com modelos LLM via Ollama, com suporte a:

- Chat textual com histórico de sessões
- Upload e processamento de anexos (PDF, imagens, arquivos de texto/código)
- Streaming de respostas em tempo real (Server-Sent Events)
- Múltiplas interfaces de usuário (Streamlit e HTML5 puro)

**Casos de uso principais:**
- Uso profissional com dados sensíveis (sem envio para cloud)
- Desenvolvimento e estudo de LLMs sem custos de API
- Análise de dados e documentos com modelos locais

---

## 2. Capacidades Principais

### 2.1 Chat com Histórico de Sessões
- Criação automática de sessões (UUID v4)
- Histórico limitado a 20 turnos por sessão (evita context overflow)
- Limpeza individual ou global de sessões
- Estado volátil (perdido ao reiniciar backend)

### 2.2 Processamento de Anexos
Suporta três tipos de arquivos:

| Tipo | Extensões | Processamento |
|---|---|---|
| **PDF** | `.pdf` | Extração de texto (pypdf + PyMuPDF); se < 80 chars não-brancos, rasteriza páginas como PNG via PyMuPDF (máx. 5 páginas) |
| **Imagem** | `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif` | Redimensiona se > 2048px, converte para PNG base64 |
| **Texto/Código** | `.txt`, `.csv`, `.json`, `.py`, `.js`, `.md`, etc. | Lê como UTF-8, trunca em 80.000 caracteres (metade início + metade fim) |

**Limite de arquivo:** 15 MB

### 2.3 Streaming via SSE
- **Todos os endpoints de chat (`/chat` e `/chat/upload`) retornam SSE streaming por padrão** — não existe mais modo síncrono (resposta completa) nem endpoint `/chat/stream` dedicado
- Painel de "thinking" colapsável para modelos com raciocínio interno
- Session ID enviado como primeiro evento SSE (`type: "start"`)
- Tokens individuais enviados como eventos `type: "token"`
- Evento `type: "done"` sinaliza conclusão com `tokens_used`

### 2.4 Configuração de Parâmetros do Modelo
- Modelo (selecionado dinamicamente do Ollama)
- Temperature (0.0 – 2.0)
- Top P (0.0 – 1.0)
- Top K (0 – 100000)
- Max Tokens (64 – 8192)
- Thinking (on/off para modelos compatíveis)
- System Prompt (texto livre)

---

## 3. Stack Tecnológica

| Camada | Tecnologia | Versão | Função |
|---|---|---|---|
| **LLM Runtime** | Ollama | local | Serve modelos LLM via API REST (porta 11434) |
| **Backend Framework** | FastAPI | 0.115.6 | API REST assíncrona |
| **Backend Server** | Uvicorn | 0.32.1 | Servidor ASGI |
| **HTTP Client** | httpx | 0.28.1 | Cliente HTTP assíncrono |
| **Validação** | Pydantic | 2.10.4 | Esquemas de dados |
| **PDF texto** | pypdf | 5.1.0 | Extração de texto de PDFs |
| **PDF raster** | PyMuPDF (fitz) | 1.25.3 | Rasterização de páginas PDF como imagem |
| **Imagem** | Pillow | 11.0.0 | Processamento/redimensionamento de imagens |
| **Upload** | python-multipart | 0.0.20 | Parse de multipart/form-data |
| **Frontend principal** | Streamlit | 1.41.1 | Interface de chat reativa (porta 8501) |
| **Frontend alternativo** | Python stdlib (http.server) | — | Servidor HTTP para HTML5 puro (porta 8502) |
| **Frontend JS libs** | marked (CDN) | ~12.0.2 | Renderização Markdown no HTML5 |
| **Frontend JS libs** | DOMPurify (CDN) | ~3.2.2 | Sanitização de HTML |

**Modelo padrão:** `gemma4:e2b`

**Portas:**
- Backend FastAPI: **8500** (configurável via env `PORT`)
- Frontend Streamlit: **8501**
- Frontend HTML5: **8502**
- Ollama: **11434**

---

## 4. Arquitetura de Alto Nível

```
┌──────────────────────────────────────────────────────┐
│                  Navegador (Browser)                 │
│                                                      │
│  ┌──────────────────┐    ┌──────────────────────┐   │
│  │  Streamlit UI    │    │  HTML5/JS UI         │   │
│  │  (porta 8501)    │    │  (porta 8502)        │   │
│  └────────┬─────────┘    └──────────┬───────────┘   │
└───────────┼─────────────────────────┼───────────────┘
            │   HTTP REST (POST/GET)  │
            ▼                         ▼
┌──────────────────────────────────────────────────────┐
│              Backend FastAPI (porta 8500)            │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  api.py — Endpoints REST                     │   │
│  │  • /health, /models, /stack-info             │   │
│  │  • /chat, /chat/upload                                 │   │
│  │  • /session/{id}, /sessions                            │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  attachments.py — Processamento de arquivos  │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  sessions: dict (memória, volátil)           │   │
│  └──────────────────────────────────────────────┘   │
└────────────────────────┬─────────────────────────────┘
                         │ HTTP (POST /api/chat)
                         ▼
┌──────────────────────────────────────────────────────┐
│                Ollama (porta 11434)                  │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  Modelos: gemma4:e2b (padrão), outros        │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

---

## 5. Componentes Principais

### 5.1 `backend/api.py` (~530 linhas)
**Responsabilidade:** API REST completa

**Endpoints:**
- `GET /health` — Health check da API + status do Ollama
- `GET /stack-info` — Diagnóstico de versão/caminho do módulo attachments
- `GET /models` — Lista modelos disponíveis no Ollama
- `POST /chat` — Chat com streaming SSE (token por token) — substituiu o antigo modo síncrono
- `POST /chat/upload` — Chat com upload de arquivo (multipart/form-data), streaming SSE — substituiu o antigo modo síncrono
- `GET /session/{id}` — Histórico de uma sessão
- `DELETE /session/{id}` — Limpa histórico de uma sessão
- `DELETE /sessions` — Limpa todas as sessões

**Nota:** O endpoint `/chat/stream` foi removido. Ambos `/chat` e `/chat/upload` agora retornam SSE streaming como modo padrão e único.

**Gerenciamento de sessões:** dict em memória com histórico limitado a 20 turnos (`MAX_HISTORY`)

**Lifespan:** Verifica conexão com Ollama na inicialização

### 5.2 `backend/attachments.py` (~300 linhas)
**Responsabilidade:** Classificar e processar arquivos anexados

**Função principal:** `process_attachment(filename, content_type, data) -> AttachmentOutcome`

**Regras de processamento:**
- PDF: extrai texto com pypdf + PyMuPDF (usa melhor resultado); se < 80 chars não-brancos, rasteriza páginas como PNG
- Imagem: redimensiona se > 2048px, converte para PNG base64
- Texto/código: lê como UTF-8, trunca em 80.000 caracteres
- Função `compose_user_message(user_text, outcome)` junta texto do usuário com conteúdo do anexo

### 5.3 `frontend/app.py` (~500 linhas)
**Responsabilidade:** Interface de chat Streamlit

**Recursos:**
- Sidebar com controles (modelo, temperatura, top_p, top_k, max_tokens, thinking, system prompt)
- Métricas de sessão (mensagens, tokens)
- Botão de anexar arquivo (via tkinter file dialog)
- Balões diferenciados por papel (usuário vs assistente)
- Barra de input fixa no rodapé via CSS

### 5.4 `frontend/app_web.py`
**Responsabilidade:** Servidor HTTP standalone para frontend HTML5

**Implementação:** Usa `http.server.SimpleHTTPRequestHandler` + `ThreadingHTTPServer` da stdlib Python

**Configurável:** Variáveis de ambiente `WEB_PORT` (default 8502) e `WEB_HOST`

### 5.5 `frontend/web/app.js` (~350 linhas)
**Responsabilidade:** Lógica JavaScript do frontend HTML5

**Recursos:**
- Streaming SSE com painel de "thinking" colapsável
- Renderização Markdown (marked + DOMPurify)
- Auto-resize do textarea
- Sidebar responsiva com overlay em mobile
- API resolvida dinamicamente: localStorage `las_api_base` ou detecta host/porta automaticamente

### 5.6 `frontend/web/styles.css` (~550 linhas)
**Design system:** CSS custom properties, tema dark com vinho (#8b1a1a)

**Responsivo:** Sidebar vira drawer em telas < 860px

---

## 6. Fluxos Core End-to-End

### 6.1 Chat sem Anexo
```
1. Usuário digita mensagem no frontend (Streamlit ou HTML5)
2. Frontend envia POST /chat para Backend
3. Backend:
   a. Gera/valida session_id (UUID)
   b. Monta lista de mensagens com histórico (máx 20 turnos)
   c. Envia POST para Ollama /api/chat com modelo, mensagens, parâmetros
4. Ollama processa e retorna resposta em stream
5. Backend encaminha tokens individualmente via SSE ao frontend
6. Backend salva par (user, assistant) no histórico da sessão ao final (evento "done")
7. Frontend acumula tokens e exibe balão do assistente
```

### 6.2 Chat com Anexo
```
1. Usuário seleciona arquivo (tkinter no Streamlit, <input> no HTML5)
2. Frontend envia POST /chat/upload (multipart/form-data) ao Backend
3. Backend (attachments.py):
   a. Classifica arquivo (PDF, imagem, texto) por extensão + MIME type
   b. PDF → extrai texto (pypdf + PyMuPDF); se pouco texto, rasteriza páginas como PNG base64
   c. Imagem → redimensiona, converte para PNG base64
   d. Texto → lê UTF-8, trunca se necessário
   e. Monta mensagem combinando texto extraído + pergunta do usuário
4. Envia ao Ollama com array "images" (base64) se houver imagens
5. Resposta retorna em streaming SSE com metadados do processamento do anexo
```

### 6.3 Inicialização Completa (script)
```
1. Verifica Ollama instalado
2. Inicia ollama serve em background (se não estiver rodando)
3. Baixa modelo gemma4:e2b (se não existir)
4. Cria venv do backend, instala deps, sobe uvicorn em background
5. Health check no backend
6. Cria venv do frontend, instala deps, sobe streamlit
7. Abre navegador em http://localhost:8501
```

---

## 7. Regras de Negócio e Invariantes

### 7.1 Invariantes Críticos (NÃO quebrar)
1. **Histórico limitado:** Máximo 20 turnos por sessão (`MAX_HISTORY = 20`)
2. **Limite de arquivo:** 15 MB máximo
3. **Truncamento de texto:** 80.000 caracteres máximo para arquivos de texto
4. **Rasterização PDF:** Máximo 5 páginas como imagem
5. **Threshold de texto PDF:** < 80 caracteres não-brancos → rasteriza como imagem
6. **CORS:** `allow_origins=["*"]` (projetado para uso local isolado)

### 7.2 Regras de Processamento
- PDFs com extração de texto fraca (scanned ou sem texto) são rasterizados como imagens
- Imagens grandes são redimensionadas para máximo 2048px na maior dimensão
- Arquivos de texto longos são truncados com aviso visível
- Sessões são voláteis (perdidas ao reiniciar backend)
- Sem autenticação ou mecanismo de autorização

---

## 8. Áreas de Complexidade e Riscos

### 8.1 Inconsistência de Portas
- `api.py` usa porta **8500** por default (via env `PORT`)
- `backend/start.sh` usa porta **8500**
- `windows_start_all.bat` usa porta **8500**
- `backend/test_api.sh` usa porta **8500** (atualizado)

**Status:** Portas consistentes em todos os scripts. Sem riscos conhecidos de inconsistência.

### 8.2 Modelo Padrão Alterado
- Código usa `gemma4:e2b` como modelo padrão
- Documentação ainda menciona `qwen3.5:4b`

**Risco:** Usuários seguindo documentação podem instalar modelo errado.

### 8.3 Sem Persistência
- Sessões são inteiramente em memória
- Reiniciar backend perde todo histórico

**Risco:** Perda de contexto conversacional ao reiniciar.

### 8.4 Sem Autenticação
- CORS `allow_origins=["*"]` sem mecanismo de auth

**Risco:** Seguro apenas se usado em rede local isolada. Não expor à internet.

---

## 9. Modelos Customizados Ollama

### 9.1 `analista_dados.Modelfile`
- **Base:** `gemma:4b-e4b`
- **Personalidade:** Analista de Dados Sênior
- **Comportamento:** Retorna JSON para pedidos estruturados, texto livre para perguntas exploratórias
- **Local:** `docs/Modelfiles/analista_dados.Modelfile`

---

## 10. Dependências Externas

| Dependência | Tipo | URL/Porta | Uso |
|---|---|---|---|
| **Ollama** | Serviço local | `http://localhost:11434` | Inferência LLM |
| **Google Fonts (Inter)** | CDN | `fonts.googleapis.com` | Fonte do frontend |
| **marked** | CDN (jsdelivr) | `cdn.jsdelivr.net` | Markdown parsing no HTML5 |
| **DOMPurify** | CDN (jsdelivr) | `cdn.jsdelivr.net` | HTML sanitization no HTML5 |

**Sem banco de dados.** Todo estado é volátil (memória).

**Sem serviços cloud.** 100% local.

---

## 11. Entrada Points (Comandos)

| Entry Point | Arquivo | Comando | Porta |
|---|---|---|---|
| **Script Windows completo** | `windows_start_all.bat` | `start_all.bat` | — |
| **Script Linux completo** | `linux_start_all.sh` | `bash linux_start_all.sh` | — |
| **Backend (uvicorn direto)** | `backend/api.py` | `uvicorn api:app --host 0.0.0.0 --port 8500` | **8500** |
| **Frontend Streamlit** | `frontend/app.py` | `streamlit run app.py --server.port 8501` | **8501** |
| **Frontend HTML5** | `frontend/app_web.py` | `python app_web.py` | **8502** |

---

## 12. Observações e Assunções

1. **Ambiente:** Python 3.10+ necessário
2. **SO:** Suporta Linux e Windows (scripts específicos para cada)
3. **Hardware:** Mínimo 8 GB RAM; recomendado 16 GB para modelos maiores
4. **GPU:** Não obrigatória; modelo roda via CPU
5. **Rede:** Offline após download do modelo; apenas CDN de fontes e libs JS requer internet
6. **Segurança:** Projetado para uso local isolado; não expor à internet sem auth

---

*Documento gerado com base em análise de código fonte. Última atualização: abril 2026.*
