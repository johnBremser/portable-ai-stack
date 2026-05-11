# AGENT_WORKFLOW.md — Local AI Stack

> Este documento descreve os fluxos de trabalho, automação e comportamento do sistema relacionados a agentes e orquestração. O Local AI Stack não implementa agentes AI internos; contudo, possui fluxos de inicialização automática e modelos customizados Ollama.

---

## 1. Visão Geral

O Local AI Stack **não implementa agentes AI com autonomia de decisão**. O sistema segue um padrão de arquitetura request-response clássico:

```
Usuário → Frontend → Backend → Ollama (LLM) → Backend → Frontend → Usuário
```

**O que existe em termos de automação:**
- Scripts de inicialização automática (orquestração de serviços)
- Modelo customizado Ollama (`analista_dados.Modelfile`) com comportamento específico
- Lifespan do FastAPI com health check automático na inicialização

---

## 2. Scripts de Orquestração

### 2.1 `linux_start_all.sh` (Linux)

**Tipo:** Script Bash de inicialização completa

**Responsabilidade:** Automatizar subida de toda a stack (Ollama + Backend + Frontend)

**Fluxo de Execução:**

```
1. Verifica se Ollama está instalado (command -v ollama)
   │
   ├─ NÃO → Instala Ollama via curl -fsSL https://ollama.com/install.sh | sh
   └─ SIM → Continua
   │
2. Inicia Ollama em background (ollama serve &)
   │
3. Aguarda Ollama ficar disponível (loop com sleep)
   │
4. Verifica se modelo gemma4:e2b está instalado (ollama list)
   │
   ├─ NÃO → Baixa modelo (ollama pull gemma4:e2b)
   └─ SIM → Continua
   │
5. Backend:
   a. cd backend
   b. Cria venv se não existe (python -m venv .venv)
   c. Ativa venv (source .venv/bin/activate)
   d. Instala deps (pip install -r requirements.txt)
   e. Sobe uvicorn em background (python api.py &)
   f. Aguarda health check (curl localhost:8500/health)
   │
6. Frontend:
   a. cd frontend
   b. Cria venv se não existe
   c. Ativa venv
   d. Instala deps (pip install -r requirements.txt)
   e. Sobe streamlit em background (streamlit run app.py &)
   │
7. Abre navegador (xdg-open http://localhost:8501)
   │
8. Exibe mensagem de conclusão
```

**Características:**
- Idempotente (pode ser executado múltiplas vezes sem efeitos colaterais)
- Verifica existência de componentes antes de instalar
- Aguarda serviços ficarem disponíveis antes de prosseguir
- Roda todos os serviços em background

### 2.2 `windows_start_all.bat` (Windows)

**Tipo:** Batch script de inicialização completa

**Responsabilidade:** Same as Linux script, adaptado para Windows

**Diferenças para versão Linux:**
- Não instala Ollama automaticamente (requer instalação manual prévia)
- Usa `start /B` para processos em background
- Porta do backend: **8500** (consistente com o código)
- Abre navegador via `start http://localhost:8501`

**Fluxo de Execução:**

```
1. Verifica se Ollama está instalado (where ollama)
   │
   ├─ NÃO → Exibe erro e instruções para instalar manualmente
   └─ SIM → Continua
   │
2. Inicia Ollama em background (start /B ollama serve)
   │
3. Verifica se modelo gemma4:e2b está instalado
   │
   ├─ NÃO → Baixa modelo (ollama pull gemma4:e2b)
   └─ SIM → Continua
   │
4. Backend:
   a. cd backend
   b. Cria venv se não existe (python -m venv .venv)
   c. Instala deps (pip install -r requirements.txt)
   d. Sobe uvicorn em background (start /B uvicorn api:app --host 0.0.0.0 --port 8500)
   e. Aguarda health check (curl localhost:8500/health)
   │
5. Frontend:
   a. cd frontend
   b. Cria venv se não existe
   c. Instala deps
   d. Sobe streamlit (start /B streamlit run app.py --server.port 8501)
   │
6. Abre navegador (start http://localhost:8501)
```

**Nota:** Porta do backend é **8500**, consistente com `api.py` e demais scripts.

---

## 3. Modelo Customizado Ollama

### 3.1 `analista_dados.Modelfile`

**Local:** `docs/Modelfiles/analista_dados.Modelfile`

**Tipo:** Definição de modelo customizado Ollama

**Base:** `gemma:4b-e4b`

**Propósito:** Criar um agente de IA especializado em análise de dados

### 3.2 Comportamento Definido

**Personalidade:** Analista de Dados Sênior

**Regras de Comportamento:**

1. **Análise Rigorosa:** Sempre realiza análise completa antes de responder; explica lógica por trás dos resultados
2. **Formato Condicional:**
   - Pedido estruturado → Retorna **exclusivamente JSON válido**
   - Pedido aberto/exploratório → Retorna **texto livre** com introdução e conclusão analítica
3. **Tratamento de Dados:** Dados fornecidos são fonte primária; pede esclarecimentos se ambiguidade
4. **Prioridade:** Clareza e precisão > brevidade

### 3.2 Template de Saída

```
# Modelo de Resposta do Analista de Dados

## Análise Solicitada
[Análise detalhada baseada nos dados]

## Resultados
[Detalhes dos resultados ou conclusão principal]

## Observações (Opcional)
[Contexto adicional, limitações ou recomendações]

---
**Formato de Saída:** JSON ou Texto Livre (dependendo da solicitação)
```

### 3.3 Como Usar

```bash
# Criar modelo customizado
ollama create analista_dados -f docs/Modelfiles/analista_dados.Modelfile

# Usar no chat
# Selecionar "analista_dados" no dropdown de modelos do frontend
```

---

## 4. Lifespan do FastAPI (Health Check Automático)

### 4.1 Implementação

**Local:** `backend/api.py` — função `lifespan(app: FastAPI)`

**Tipo:** Context manager assíncrono executado na inicialização e encerramento

**Fluxo:**

```
STARTUP:
1. Log: "Iniciando API — verificando conexão com Ollama..."
2. GET http://localhost:11434/api/tags (timeout 5s)
   │
   ├─ SUCESSO → Log: "Ollama conectado. Modelos disponíveis: [lista]"
   └─ FALHA   → Warning: "Ollama não respondeu na inicialização: [erro]"
3. Log: "Anexos/PDF: rasterização só com PyMuPDF..."
4. Yield (API fica operacional)

SHUTDOWN:
5. Log: "API encerrada."
```

**Propósito:**
- Verificar conectividade com Ollama antes de receber requisições
- Logar modelos disponíveis para diagnóstico
- Informar engine de rasterização PDF em uso

---

## 5. Fluxos de Trabalho do Sistema

### 5.1 Fluxo de Chat Principal

```
┌─────────┐     ┌───────────┐     ┌───────────┐     ┌─────────┐
│Usuário  │────→│ Frontend  │────→│  Backend  │────→│  Ollama │
│         │     │           │     │           │     │         │
│         │←────│           │←────│           │←────│         │
└─────────┘     └───────────┘     └───────────┘     └─────────┘

Detalhamento:
1. Usuário digita mensagem + opcionalmente anexa arquivo
2. Frontend envia POST para Backend:
   - /chat (resposta completa)
   - /chat/stream (streaming SSE)
   - /chat/upload (com anexo)
3. Backend:
   a. Gera/valida session_id
   b. Recupera histórico (máx 20 turnos)
   c. Se anexo: processa via attachments.py
   d. Monta payload para Ollama
   e. Envia POST /api/chat
4. Ollama processa e retorna resposta
5. Backend salva par (user, assistant) no histórico
6. Resposta retorna ao frontend
7. Frontend exibe balão do assistente
```

### 5.2 Fluxo de Processamento de Anexos

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────┐
│  Frontend    │────→│  Backend         │────→│  attachments  │
│  (upload)    │     │  (api.py)        │     │  (.py)        │
└──────────────┘     └──────────────────┘     └───────────────┘
                            │
                            ▼
                     Classifica arquivo
                     por extensão + MIME
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          PDF           Imagem        Texto/Código
              │             │             │
              ▼             ▼             ▼
        Extrai texto   Redimensiona   Lê UTF-8
        (pypdf +       converte para  trunca se
         PyMuPDF)      PNG base64     necessário
              │
              ▼
        >= 80 chars
        não-brancos?
              │
        ┌─────┴─────┐
        ▼           ▼
      SIM          NÃO
        │           │
        ▼           ▼
     Retorna    Rasteriza
     texto      páginas
                como PNG
                (máx 5)
```

### 5.3 Fluxo de Gerenciamento de Sessões

```
Request recebido com session_id?
        │
   ┌────┴────┐
   ▼         ▼
  SIM       NÃO
   │         │
   ▼         ▼
 Session ID  Gera UUID v4
 existe?     nova
   │
 ┌─┴─┐
 ▼   ▼
SIM  NÃO
 │   │
 ▼   ▼
 Usa  Cria
 sess. nova
   │
   ▼
Monta messages com
histórico (máx 20)
   │
   ▼
Envia para Ollama
   │
   ▼
Salva (user, assistant)
no histórico
```

---

## 6. Tool Usage

O sistema não implementa ferramentas/tool calls internos. As únicas "ferramentas" disponíveis são:

| Ferramenta | Tipo | Acesso | Descrição |
|---|---|---|---|
| **Ollama API** | Serviço externo | Backend → Ollama | Inferência LLM via `/api/chat` e `/api/tags` |
| **attachments.py** | Módulo interno | Backend interno | Processamento de arquivos (PDF, imagem, texto) |
| **Health Check** | Endpoint | Externo → Backend | Verificação de status (`/health`) |

---

## 7. Observações para Agentes Externos

Se um agente AI externo (ex: Qwen Code, Cursor, etc.) for operar neste repositório:

### 7.1 O Que Pode Fazer Autonomamente
- Ler código e documentação
- Modificar endpoints da API
- Adicionar novos schemas Pydantic
- Alterar frontend (Streamlit ou HTML5)
- Adicionar testes
- Atualizar documentação

### 7.2 O Que Requer Aprovação do Usuário
- Alterar porta padrão do backend (quebra scripts)
- Mudar modelo padrão (afeta experiência do usuário)
- Adicionar dependências externas novas
- Alterar estrutura de sessões (ex: adicionar persistência)
- Modificar CORS (impacto de segurança)

### 7.3 Invariantes a Respeitar
1. Frontend nunca acessa Ollama diretamente
2. Backend gerencia sessões e histórico
3. Anexos são processados no backend
4. Histórico é limitado (MAX_HISTORY = 20)
5. Sessões são voláteis (sem persistência em disco)
6. Ollama é dependência externa obrigatória

---

*Documento alinhado com PROJECT_SPEC.md. Última atualização: abril 2026.*
