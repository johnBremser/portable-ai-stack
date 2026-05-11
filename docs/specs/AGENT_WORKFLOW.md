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

### 2.1 `start_portable.bat` (Windows)

**Tipo:** Batch script de inicialização portátil completa

**Responsabilidade:** Automatizar subida de toda a stack (Ollama + Backend + Frontend) a partir do pendrive.

**Fluxo de Execução:**

```
1. Define caminhos relativos (bin\python, bin\ollama-windows.exe)
2. Configura OLLAMA_MODELS para data\models (impede uso do disco C:)
3. Inicia Ollama Portable em background (start /min bin\ollama-windows.exe serve)
4. Inicia Backend FastAPI usando Python local (bin\python\python.exe -m uvicorn api:app)
5. Inicia Frontend HTML5 usando Python local (bin\python\python.exe app_web.py)
6. Abre navegador em http://localhost:8502
```

**Características:**
- Idempotente (pode ser executado múltiplas vezes sem efeitos colaterais)
- Verifica existência de componentes antes de instalar
- Aguarda serviços ficarem disponíveis antes de prosseguir
- Roda todos os serviços em background

### 2.2 `setup_portable.bat / .ps1`

**Tipo:** Scripts de configuração inicial do pendrive

**Responsabilidade:** Baixar e configurar Python e Ollama diretamente na pasta `bin/`, tornando a stack 100% independente do sistema hospedeiro.

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
- Garantir que o Banco de Dados SQLite está inicializado (`init_db`)
- Verificar conectividade com Ollama antes de receber requisições
- Logar modelos disponíveis para diagnóstico
- Informar engine de rasterização PDF em uso

---

## 5. Fluxos de Trabalho do Sistema

### 5.1 Fluxo de Chat Principal

```
┌─────────┐     ┌───────────┐     ┌───────────┐     ┌─────────┐
│Usuário  │────→│ Frontend  │────→│  Backend  │────→│  Ollama │
│         │     │ (HTML5)   │     │ (api.py)  │     │         │
│         │←────│           │←────│           │←────│         │
└─────────┘     └───────────┘     └───────────┘     └─────────┘

Detalhamento:
1. Usuário digita mensagem + opcionalmente anexa arquivo
2. Frontend envia POST para Backend:
   - /chat (streaming SSE)
   - /chat/upload (com anexo, streaming SSE)
3. Backend:
   a. Gera/valida session_id
   b. Recupera histórico (máx 20 turnos)
   c. Se anexo: processa via attachments.py
   d. Monta payload para Ollama
   e. Envia POST /api/chat
4. Ollama processa e retorna resposta
5. Backend salva par (user, assistant) no SQLite
6. Resposta retorna ao frontend em tempo real (SSE)
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
 Busca no    Gera UUID v4
 SQLite      nova
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
no SQLite (sessions.db)
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
- Alterar frontend (HTML5)
- Adicionar testes
- Atualizar documentação

### 7.2 O Que Requer Aprovação do Usuário
- Alterar porta padrão do backend (quebra scripts)
- Mudar modelo padrão (afeta experiência do usuário)
- Adicionar dependências externas novas
- Alterar estrutura de sessões (já implementado via SQLite)
- Modificar CORS (impacto de segurança)

### 7.3 Invariantes a Respeitar
1. Frontend nunca acessa Ollama diretamente
2. Backend gerencia sessões e histórico
3. Anexos são processados no backend
4. Histórico é limitado (MAX_HISTORY = 20)
5. Sessões são persistidas em SQLite (sessions.db)
6. Ollama é dependência externa obrigatória

---

*Documento alinhado com PROJECT_SPEC.md. Última atualização: abril 2026.*
