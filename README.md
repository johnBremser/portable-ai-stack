# 🤖 Portable AI Stack

> Stack completa e **100% portátil** para chat com **LLMs locais** via Ollama.  
> Roda direto de um pendrive — sem cloud, sem instalação no Windows, sem custos de API.
> Backend em **FastAPI** · Frontend em **HTML5/JS Moderno** · Modelo padrão: **Qwen3.5:4b**

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Portable-black?style=flat)
![License](https://img.shields.io/badge/License-MIT-8B1A1A?style=flat)

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura Portátil](#arquitetura-portátil)
- [Instalação (Setup do Pendrive)](#instalação-setup-do-pendrive)
- [Como Usar](#como-usar)
- [Endpoints da API](#endpoints-da-api)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Especificações SDD (Para Agentes e Desenvolvedores)](#especificações-sdd-para-agentes-e-desenvolvedores)

---

## Visão Geral

O **Portable AI Stack** é uma solução para levar sua própria IA em um USB drive. Ele configura um ambiente Python isolado e uma instância do Ollama que armazena modelos e dados diretamente no dispositivo removível. Ideal para ambientes corporativos restritos ou para manter privacidade total em qualquer computador Windows.

| Camada | Tecnologia | Função |
|---|---|---|
| **LLM Runtime** | Ollama Portable | Serve o modelo localmente (isolado em `/bin`) |
| **Backend** | FastAPI | Gerencia sessões (SQLite), histórico e streaming |
| **Frontend** | HTML5/JS/CSS | Interface de chat premium com suporte a Markdown |
| **Modelo padrão** | Qwen3.5:4b | Otimizado para hardware com 8-16 GB RAM |

---

## Arquitetura Portátil

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
│              │  • /chat/upload │                        │
│              └────────┬────────┘                        │
└───────────────────────┼─────────────────────────────────┘
                        │ HTTP (Portátil)
                        ▼
┌─────────────────────────────────────────────────────────┐
│              http://localhost:11434                     │
│                                                         │
│              ┌─────────────────┐                        │
│              │     Ollama      │                        │
│              │  (data/models)  │                        │
│              └─────────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

**Diferencial Portátil:** O Ollama é configurado via variável de ambiente `OLLAMA_MODELS` para apontar para a pasta `data/models` dentro do pendrive, impedindo que ele use espaço no disco `C:` do computador hospedeiro.

---

## Instalação (Setup do Pendrive)

Se você acabou de baixar o projeto para o seu pendrive/pasta local:

1. **Execute o Setup:**
   - No Windows, clique duas vezes em `setup_portable.bat`.
   - Isso irá baixar o Python Embeddable, o Ollama EXE e todas as bibliotecas necessárias para a pasta `bin/`.

2. **Aguarde a Conclusão:**
   - O script criará as pastas `bin` e `data`.
   - Não é necessário ter Python ou Ollama instalados no Windows previamente.

---

## Como Usar

### ▶ Inicialização Rápida

Basta executar o arquivo na raiz do projeto:

```
start_portable.bat
```

O script fará o seguinte:

1. Sobe o **Ollama Portable** em background.
2. Inicia o **Backend FastAPI** na porta `8500`.
3. Inicia o **Frontend Web** e abre o navegador em `http://localhost:8502`.

---

## Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Status da API e do Ollama |
| `GET` | `/models` | Modelos disponíveis no Ollama |
| `POST` | `/chat` | Chat com streaming (SSE) |
| `POST` | `/chat/upload` | Chat com anexo e streaming (SSE) |
| `GET` | `/sessions` | Lista todas as sessões ativas |
| `DELETE` | `/session/{id}` | Remove uma sessão específica |

---

## Estrutura do Projeto

```
portable-ai-stack/
├── setup_portable.bat      # Baixa Python e Ollama para o pendrive
├── start_portable.bat      # Inicializa toda a stack
├── bin/                    # Binários portáteis (Python, Ollama)
├── data/
│   ├── models/             # Onde os modelos do Ollama ficam salvos
│   └── sessions.db         # Banco SQLite com histórico de chat
├── backend/
│   ├── api.py              # API FastAPI
│   └── attachments.py      # Gestão de anexos/arquivos
├── frontend/
│   ├── app_web.py          # Servidor estático
│   └── web/                # HTML/JS/CSS da interface
└── docs/                   # Documentação detalhada
```

---

## 📜 Especificações SDD (Para Agentes e Desenvolvedores)

Este projeto segue **Spec-Driven Development (SDD)**. A fonte de verdade está em `/docs/specs/`.

1. **[PROJECT_SPEC.md](docs/specs/PROJECT_SPEC.md)** — Visão geral e invariantes.
2. **[ARCHITECTURE.md](docs/specs/ARCHITECTURE.md)** — Fluxos de dados e camadas.
3. **[API_CONTRACTS.md](docs/specs/API_CONTRACTS.md)** — Detalhamento dos endpoints.
4. **[DEVELOPMENT_GUIDE.md](docs/specs/DEVELOPMENT_GUIDE.md)** — Como estender o sistema.

---

## Referências

- [Ollama](https://ollama.com)
- [FastAPI](https://fastapi.tiangolo.com)
- [Qwen Models](https://huggingface.co/Qwen)
