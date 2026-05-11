# 🤖 Local AI Stack

> Stack completa para chat com **LLMs locais** via Ollama — sem cloud, sem custos de API, sem envio de dados externos.  
> Backend em **FastAPI** · Frontend em **Streamlit** · Modelo padrão: **Qwen3.5:4b**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.41-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-local-black?style=flat)
![License](https://img.shields.io/badge/License-MIT-8B1A1A?style=flat)

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Execução](#execução)
  - [▶ Execução rápida (recomendado)](#-execução-rápida-recomendado)
  - [▶ Execução manual](#-execução-manual)
- [Endpoints da API](#endpoints-da-api)
- [Requisitos de Hardware](#requisitos-de-hardware)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Especificações SDD (Para Agentes e Desenvolvedores)](#especificações-sdd-para-agentes-e-desenvolvedores)
- [Referências](#referências)

---

## Visão Geral

O **Local AI Stack** é uma aplicação de chat com modelos de linguagem que roda inteiramente na máquina local. Nenhum dado é enviado para servidores externos — ideal para uso profissional com informações sensíveis ou para desenvolvimento e estudo de LLMs sem custos de API.

| Camada | Tecnologia | Função |
|---|---|---|
| **LLM Runtime** | Ollama | Serve o modelo localmente com API REST |
| **Backend** | FastAPI + httpx | Gerencia sessões, histórico e roteamento |
| **Frontend** | HTML5 Moderno, Javascript (Vanilla), CSS3 | Interface de chat com identidade visual customizada |
| **Modelo padrão** | Qwen3.5:4b | Otimizado para hardware com 16 GB RAM sem GPU |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                     Navegador                           │
│              http://localhost:8502                      │
│                                                         │
│              ┌─────────────────┐                        │
│              │   HTML5/JS UI   │                        │
│              │   (frontend)    │                        │
│              └────────┬────────┘                        │
└───────────────────────┼─────────────────────────────────┘
                        │ HTTP REST
                        ▼
┌─────────────────────────────────────────────────────────┐
│              http://localhost:8500                      │
│                                                         │
│              ┌─────────────────┐                        │
│              │   FastAPI API   │                        │
│              │   (backend)     │                        │
│              │                 │                        │
│              │  • /chat        │                        │
│              │  • /chat/stream │                        │
│              │  • /models      │                        │
│              │  • /health      │                        │
│              └────────┬────────┘                        │
└───────────────────────┼─────────────────────────────────┘
                        │ HTTP
                        ▼
┌─────────────────────────────────────────────────────────┐
│              http://localhost:11434                     │
│                                                         │
│              ┌─────────────────┐                        │
│              │     Ollama      │                        │
│              │  qwen3.5:4b     │                        │
│              └─────────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

**Fluxo:** `Usuário digita` → `Frontend` → `FastAPI (gerencia sessão)` → `Ollama (infere)` → `resposta retorna pela mesma cadeia`

---

## Pré-requisitos

- Python **3.10+**
- [Ollama](https://ollama.com/download) instalado
- Conexão com internet apenas para baixar o modelo (execução é 100% offline)

---

## Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/faanogueira/local-ai-stack.git
cd local-ai-stack
```

### 2. Instalar o Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

![Install Ollama](/backend/img/install_ollama.png)

### 3. Baixar o modelo

```bash
ollama pull qwen3.5:4b
```

![Install Qwen3.5:4b](/backend/img/install_qwen3-5:4b.png)

> **Modelos alternativos:** `qwen3.5:9b` (requer 16 GB+ RAM com GPU) · `qwen3.5:2b` (hardware mais limitado)

### 4. Instalar dependências do backend

```bash
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python ./api.py

cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; python ./api.py
```

### 5. Instalar dependências do frontend

```bash
cd frontend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python ./app_web.py

cd frontend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; python ./app_web.py
```

---

## Execução

### ▶ Execução rápida (recomendado)

Um único arquivo inicializa toda a stack automaticamente — Ollama, backend e frontend.

**Linux:**

```bash
chmod +x start_all.sh
bash start_all.sh
```

![Rodando linux_start_all.sh](/backend/img/run_bash.png)

**Windows:**

```
start_all.bat
```

> No Windows, o Ollama precisa estar instalado manualmente antes de executar o script.  
> Download: [ollama.com/download](https://ollama.com/download)

O script realiza automaticamente:

1. Verifica (e instala, no Linux) o Ollama
2. Sobe o servidor Ollama em background
3. Baixa o modelo `qwen3.5:4b` se ainda não estiver disponível
4. Cria os ambientes virtuais, instala as dependências e sobe o backend
5. Instala as dependências e abre o frontend no navegador

![Agente em funcionamento](/backend/img/run_agent.png)

---

### ▶ Execução manual

Para quem preferir controle total, abra **três terminais** e execute em ordem:

```bash
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — Backend
cd backend && bash start.sh

# Terminal 3 — Frontend
cd frontend && bash start.sh
```

---

| Serviço | URL |
|---|---|
| O frontend (HTML5) abrirá em: | <http://localhost:8502> |
| API REST | <http://localhost:8000> |
| Documentação da API (Swagger) | <http://localhost:8000/docs> |

---

## Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Status da API e do Ollama |
| `GET` | `/models` | Modelos disponíveis no Ollama |
| `POST` | `/chat` | Chat com resposta completa |
| `POST` | `/chat/stream` | Chat com streaming (SSE) |
| `GET` | `/session/{id}` | Histórico de uma sessão |
| `DELETE` | `/session/{id}` | Limpa histórico da sessão |

Exemplo de requisição:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "O que é um Large Language Model?",
    "model": "qwen3.5:4b",
    "temperature": 0.7
  }'
```

---

## Requisitos de Hardware

| Componente | Mínimo | Testado |
|---|---|---|
| **RAM** | 8 GB | 16 GB |
| **CPU** | x86-64 dual-core | Intel i5 8ª geração |
| **GPU** | Não obrigatória | — |
| **Armazenamento** | 5 GB livres | SSD recomendado |
| **SO** | Ubuntu 20.04+ / macOS 12+ | Ubuntu 24.04 LTS |

> Sem GPU dedicada, o modelo roda via CPU. No hardware de referência (i5-8365U, 16 GB RAM), o Qwen3.5:4b gera entre 3–8 tokens/segundo — funcional para uso individual.

---

## Estrutura do Projeto

```
local-ai-stack/
├── start_all.sh            # Execução rápida — Linux
├── start_all.bat           # Execução rápida — Windows
├── .gitignore
├── backend/
│   ├── api.py              # API FastAPI — endpoints, sessões, streaming
│   ├── requirements.txt
│   ├── start.sh
│   ├── test_api.sh         # Testes dos endpoints via curl
│   └── README.md
├── frontend/
│   ├── app.py              # Interface Streamlit
│   ├── requirements.txt
│   ├── start.sh
│   ├── README.md
│   └── .streamlit/
│       └── config.toml     # Tema customizado
└── README.md
```

---

## 📜 Especificações SDD (Para Agentes e Desenvolvedores)

> **⚠️ Para agentes de IA e orquestradores:** Este projeto segue Spec-Driven Development (SDD).
> A fonte de verdade para entender, estender e operar o sistema está em `/docs/specs/`.

### Ordem de Leitura Recomendada

1. **[PROJECT_SPEC.md](docs/specs/PROJECT_SPEC.md)** — Fonte principal de verdade (propósito, capacidades, stack, fluxos core)
2. **[ARCHITECTURE.md](docs/specs/ARCHITECTURE.md)** — Arquitetura detalhada, camadas, fluxos de dados
3. **[API_CONTRACTS.md](docs/specs/API_CONTRACTS.md)** — Contrato completo da API REST (endpoints, schemas, exemplos)
4. **[AGENT_WORKFLOW.md](docs/specs/AGENT_WORKFLOW.md)** — Fluxos de trabalho, orquestração, modelos customizados
5. **[DEVELOPMENT_GUIDE.md](docs/specs/DEVELOPMENT_GUIDE.md)** — Setup, execução, convenções, como estender com segurança
6. **[TESTING_SPEC.md](docs/specs/TESTING_SPEC.md)** — Estratégia de testes, mapeamento funcionalidade → teste, exemplos

### Para Agentes de IA

Ao operar neste repositório:

- Leia **PROJECT_SPEC.md** primeiro para entender o sistema
- Consulte **API_CONTRACTS.md** antes de modificar endpoints
- Respeite os **invariantes críticos** listados em PROJECT_SPEC.md e DEVELOPMENT_GUIDE.md
- Não altere portas padrão, modelo default ou estrutura de sessões sem aprovação

---

## Referências

- [Ollama — Documentação oficial](https://ollama.com)
- [Qwen3.5 — Hugging Face](https://huggingface.co/Qwen/Qwen3.5-397B-A17B)
- [FastAPI — Documentação](https://fastapi.tiangolo.com)
- [Streamlit — Documentação](https://docs.streamlit.io)

# Start frontend

```bash
cd frontend
.venv\Scripts\activate.bat
python app_web.py
```
#   p o r t a b l e - a i - s t a c k  
 