# DEVELOPMENT_GUIDE.md — Local AI Stack

> Guia para desenvolvedores configurar ambiente, executar, estender e manter o sistema de forma segura.

---

## 1. Setup do Ambiente de Desenvolvimento

### 1.1 Pré-requisitos

| Componente | Versão | Obrigatório | Como Instalar |
|---|---|---|---|
| **Python** | 3.10+ | Sim | `python --version` |
| **Ollama** | Latest | Sim | https://ollama.com/download |
| **Git** | Any | Sim (para clone) | `git --version` |
| **curl** | Any | Sim (para testes) | `curl --version` |

**Hardware mínimo:**
- RAM: 8 GB (16 GB recomendado)
- CPU: x86-64 dual-core
- GPU: Não obrigatória
- Armazenamento: 5 GB livres

### 1.2 Clone do Repositório

```bash
git clone https://github.com/faanogueira/local-ai-stack.git
cd local-ai-stack
```

### 1.3 Instalação do Ollama

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
- Download em https://ollama.com/download
- Executar instalador

**Iniciar serviço:**
```bash
ollama serve
```

### 1.4 Download do Modelo

```bash
ollama pull gemma4:e2b
```

> **Modelo alternativo:** `ollama pull qwen3.5:4b`

### 1.5 Setup do Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv .venv

# Ativar (Windows)
.venv\Scripts\activate

# Ativar (Linux/Mac)
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Verificar instalação
python -c "import fastapi; print(fastapi.__version__)"
```

### 1.6 Setup do Frontend

Como o frontend usa apenas arquivos estáticos (HTML5/JS), não há dependências Python obrigatórias, mas o servidor `app_web.py` usa apenas a biblioteca padrão do Python.

```bash
cd ../frontend
# Nenhuma instalação de dependências necessária
```

---

## 2. Como Executar o Projeto

### 2.1 Execução Portátil (Recomendado)

**Windows:**
```cmd
start_portable.bat
```

Este script automatiza:
1. Verificação e inicialização do Ollama Portable
2. Download do modelo (se necessário)
3. Inicialização do backend FastAPI (porta 8500)
4. Inicialização do frontend HTML5 (porta 8502)
5. Abertura do navegador

### 2.2 Execução Manual (3 Terminais)

**Terminal 1 — Ollama:**
```bash
bin\ollama-windows.exe serve
```

**Terminal 2 — Backend:**
```bash
cd backend
..\bin\python\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8500
```

**Terminal 3 — Frontend:**
```bash
cd frontend
..\bin\python\python.exe app_web.py
```

### 2.3 URLs de Acesso

| Serviço | URL |
|---|---|
| Frontend HTML5 | http://localhost:8502 |
| Backend API | http://localhost:8500 |
| Swagger UI | http://localhost:8500/docs |
| ReDoc | http://localhost:8500/redoc |
| Ollama | http://localhost:11434 |

### 2.4 Health Check

```bash
curl http://localhost:8500/health
```

**Resposta esperada:**
```json
{
  "api": "online",
  "ollama": "online",
  "models": ["gemma4:e2b"],
  "sessions_active": 0
}
```

---

## 3. Como Executar Testes

### 3.1 Testes Manuais da API

```bash
cd backend
bash test_api.sh
```

**Endpoints testados:**
1. `GET /health` — Health check
2. `GET /models` — Lista modelos
3. `POST /chat` — Chat com streaming SSE
4. `GET /sessions` — Lista todas as sessões
5. `GET /session/{id}` — Histórico da sessão

### 3.2 Teste de Upload

```bash
curl -X POST http://localhost:8500/chat/upload \
  -F "file=@teste.txt" \
  -F "message=Analise este arquivo"
```

### 3.3 Teste de Streaming

```bash
curl -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Olá", "model": "qwen3.5:4b"}'
```

---

## 4. Convenções de Código Detectadas

### 4.1 Python

**Estilo:**
- Comentários de seção com `#` + `=` (ex: `# ====`)
- Docstrings em funções públicas
- Logging com `logging.getLogger(__name__)`
- Type hints em assinaturas de função
- Dataclasses para estruturas simples (`@dataclass`)

**Imports:**
- Agrupados por categoria (stdlib, third-party, local)
- Ordenados alfabeticamente dentro de cada grupo
- Imports locais para dependências opcionais (ex: `fitz` dentro de try/except)

**Nomes:**
- snake_case para funções e variáveis
- UPPER_SNAKE_CASE para constantes
- PascalCase para classes

**Tratamento de Erros:**
- `try/except` explícito com logging
- Exceptions customizadas (`AttachmentError`)
- HTTPException do FastAPI para erros de API

### 4.2 JavaScript

**Estilo:**
- IIFE (Immediately Invoked Function Expression) para encapsulamento
- `const` e `let` (sem `var`)
- CamelCase para funções e variáveis
- Async/await para operações assíncronas
- DOM manipulation via `document.getElementById`, `createElement`, etc.

### 4.3 CSS

**Estilo:**
- CSS Custom Properties (variáveis CSS)
- Classes BEM-like (ex: `.msg-user`, `.msg-assistant`)
- Media queries para responsividade
- Temas dark com cores específicas (vinho #8B1A1A)

---

## 5. Como Estender o Sistema com Segurança

### 5.1 Adicionar Novo Endpoint

**Local:** `backend/api.py`

**Passos:**
1. Definir schema Pydantic (se necessário)
2. Criar função decorada com `@app.<method>("<route>")`
3. Adicionar tratamento de erros (try/except)
4. Documentar com docstring
5. Testar via curl ou Swagger UI
6. Atualizar API_CONTRACTS.md

**Exemplo:**
```python
class NovoRequest(BaseModel):
    campo: str = Field(..., min_length=1)

@app.post("/novo-endpoint")
async def novo_endpoint(req: NovoRequest):
    """Descrição do endpoint."""
    try:
        # Lógica
        return {"resultado": "sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 5.2 Adicionar Tipo de Arquivo Suportado

**Local:** `backend/attachments.py`

**Passos:**
1. Adicionar extensões a `TEXT_EXTENSIONS`, `IMAGE_EXTENSIONS`, ou criar nova frozenset
2. Criar função `_process_novo_tipo(filename, data)`
3. Adicionar detecção em `_is_probably_*` ou nova função
4. Adicionar branch em `process_attachment()`
5. Testar com arquivo real
6. Atualizar documentação

### 5.3 Adicionar Novo Frontend

**Requisitos:**
- Consumir API REST do backend (CORS `allow_origins=["*"]`)
- Usar mesmos schemas de request/response
- Manter session_id entre requisições

**Endpoints mínimos:**
- `POST /chat` ou `POST /chat/stream`
- `GET /health` (opcional, para status)
- `GET /models` (opcional, para seleção)

**Áreas de mudança:** Implementado via SQLite em `backend/api.py`. Banco em `data/sessions.db`.

### 5.5 Adicionar Autenticação

**Áreas de mudança:**
1. Middleware de autenticação no FastAPI
2. CORS (restringir `allow_origins`)
3. Frontends (incluir tokens/credentials nas requisições)

**⚠️ Risco:** Mudança de segurança crítica. Testar extensivamente.

---

## 6. Invariantes Críticos (NÃO Quebrar)

**Estes invariantes devem ser mantidos em qualquer modificação:**

| # | Invariante | Motivo |
|---|---|---|
| 1 | Histórico limitado a 20 turnos (`MAX_HISTORY`) | Evita context overflow no Ollama |
| 2 | Limite de arquivo: 15 MB | Previne consumo excessivo de memória |
| 3 | Truncamento de texto: 80.000 chars | Previne requests gigantes ao Ollama |
| 4 | Rasterização PDF: máx 5 páginas | Previne uso excessivo de memória/CPU |
| 5 | Threshold PDF texto: 80 chars não-brancos | Decisão texto vs imagem |
| 6 | CORS `allow_origins=["*"]` | Uso local isolado (não expor à internet) |
| 7 | Sessões persistidas em SQLite | Design decision (persistência no pendrive) |
| 8 | Frontend nunca acessa Ollama diretamente | Separação de concerns |
| 9 | Anexos processados no backend | Segurança e consistência |

---

## 7. Áreas de Complexidade e Atenção

### 7.1 Processamento de PDF

**Complexidade:** Alta

**Motivo:** Duas estratégias de extração (texto vs imagem), múltiplas bibliotecas (pypdf, PyMuPDF), decisão dinâmica baseada em threshold.

**Pontos de atenção:**
- `_extract_pdf_text()` usa pypdf E PyMuPDF (compara resultados)
- `_pdf_pages_as_images()` rasteriza com matriz 2x (fitz.Matrix(2.0, 2.0))
- Threshold `MIN_PDF_TEXT_CHARS = 80` é empírico

### 7.2 Streaming SSE

**Complexidade:** Média

**Motivo:** Parser de SSE no frontend, gerenciamento de estado de stream, painéis de thinking colapsáveis.

**Pontos de atenção:**
- Buffer de lines no frontend (`buf.split("\n\n")`)
- `think` tokens aparecem antes de `content` em modelos com raciocínio
- `sawContent` flag para colapsar thinking panel

### 7.3 Gerenciamento de Sessões

**Complexidade:** Baixa

**Motivo:** Dict simples em memória, mas sem limpeza automática.

**Pontos de atenção:**
- Sem expiração de sessões (acumulam até reinício)
- `MAX_HISTORY` limita turnos, não número de sessões
- `DELETE /sessions` limpa tudo

### 7.4 Inconsistência de Portas

**Complexidade:** Média (risco de confusão)

**Situação:**
- `api.py`: default 8500 (via env `PORT`)
- `backend/start.sh`: 8500
- `start_portable.bat`: 8500
- `test_api.sh`: 8500

**Recomendação:** Padronizar para 8500 em todos os arquivos.

---

## 8. Estrutura do Projeto

```
portable-ai-stack/
├── setup_portable.bat              # Setup completo do pendrive
├── start_portable.bat              # Inicialização rápida
├── bin/                            # Binários (Python, Ollama)
├── data/                           # Dados (Modelos, SQLite)
├── backend/
│   ├── api.py                      # API FastAPI
│   ├── attachments.py              # Processamento de anexos
│   ├── requirements.txt            # Dependências Python
│   ├── README.md                   # Documentação do backend
│   └── test_api.sh                 # Testes manuais via curl
└── frontend/
    ├── app_web.py                  # Servidor HTTP para HTML5
    ├── web/                        # Interface de usuário
    └── README.md                   # Documentação do frontend
```

---

## 9. Comandos Úteis

### 9.1 Backend

```bash
# Rodar com auto-reload
uvicorn api:app --host 0.0.0.0 --port 8500 --reload

# Rodar via Python direto
python api.py

# Limpar cache (bytecode)
rm -rf __pycache__/
# Ou Windows:
rmdir /s /q __pycache__
```

### 9.2 Frontend

```bash
# HTML5 principal
python app_web.py

# HTML5 alternativo
python app_web.py
```

### 9.3 Ollama

```bash
# Listar modelos
ollama list

# Baixar modelo
ollama pull gemma4:e2b

# Remover modelo
ollama rm qwen3.5:4b

# Criar modelo customizado
ollama create analista_dados -f docs/Modelfiles/analista_dados.Modelfile
```

### 9.4 Git

```bash
# Verificar status
git status

# Commit
git add .
git commit -m "descrição das mudanças"

# Pull
git pull origin main
```

---

## 10. Debug e Troubleshooting

### 10.1 Backend não inicia

**Sintoma:** `Ollama não respondeu na inicialização`

**Causas:**
- Ollama não está rodando
- Porta 11434 bloqueada

**Solução:**
```bash
ollama serve
curl http://localhost:11434/api/tags
```

### 10.2 Erro de CORS

**Sintoma:** `Access-Control-Allow-Origin` no browser

**Causa:** Backend não configurado com CORS

**Verificação:**
```python
# Em api.py, verificar:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    ...
)
```

### 10.3 Modelo não encontrado

**Sintoma:** `model "gemma4:e2b" not found`

**Solução:**
```bash
ollama pull gemma4:e2b
```

### 10.4 PDF não processa

**Sintoma:** `AttachmentError: O pacote PyMuPDF é necessário`

**Solução:**
```bash
cd backend
pip install pymupdf
```

### 10.5 Portas em Conflito

**Sintoma:** `Address already in use`

**Solução:**
```bash
# Linux: encontrar processo na porta
lsof -i :8500
kill -9 <PID>

# Windows: encontrar processo na porta
netstat -ano | findstr :8500
taskkill /PID <PID> /F
```

---

## 11. Boas Práticas para Contribuições

1. **Testar antes de commitar:** Executar `test_api.sh` após mudanças no backend
2. **Documentar mudanças:** Atualizar specs relevantes em `/docs/specs/`
3. **Manter invariants:** Não quebrar invariantes listados na seção 6
4. **Versionar dependencies:** Pin versions em `requirements.txt`
5. **Comitar pequeno:** Commits focados em uma mudança específica
6. **Revisar CORS e auth:** Qualquer mudança em CORS ou auth requer revisão cuidadosa

---

*Documento alinhado com PROJECT_SPEC.md. Última atualização: abril 2026.*
