# 🖥️ Frontend — Portable AI Stack (HTML5)

> Interface de chat moderna construída com **HTML5, Vanilla JavaScript e CSS3**, servida por um servidor Python leve.
> Identidade visual em vermelho vinho, preto e branco — design premium e responsivo.

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Interface](#interface)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Execução](#execução)
- [Estrutura](#estrutura)

---

## Visão Geral

O frontend é uma Single Page Application (SPA) que consome a API REST do backend. Ele oferece uma experiência de chat fluida, com suporte a Markdown, realce de sintaxe de código e interface adaptável.

| Recurso | Detalhe |
|---|---|
| Tecnologias | HTML5, JS (ES6+), CSS3 |
| Servidor | Python (http.server via `app_web.py`) |
| Porta | 8502 |
| Backend | FastAPI em `http://localhost:8500` |

---

## Interface

A interface foi projetada para ser limpa e funcional:

- **Sidebar**: Atalhos e informações do sistema.
- **Área de Chat**: Balões de mensagens estilizados, suporte a Markdown e blocos de código.
- **Responsividade**: Adapta-se a diferentes tamanhos de tela.

---

## Pré-requisitos

- Python **3.10+** (apenas para servir os arquivos estáticos)
- Backend rodando em `http://localhost:8500` → veja `../backend/README.md`

---

## Instalação

Como o frontend usa apenas arquivos estáticos, não há dependências externas pesadas.

```bash
cd frontend
# Opcional: criar venv apenas para isolamento
python3 -m venv .venv
source .venv/bin/activate
```

---

## Execução

Use o script de inicialização:

```bash
bash start.sh
```

Acesse em: `http://localhost:8502`

Ou diretamente via Python:

```bash
python app_web.py
```

---

## Estrutura

```
frontend/
├── app_web.py          # Servidor HTTP simples para os arquivos estáticos
├── start_frontend.bat  # Inicialização individual
└── web/                # Pasta raiz dos arquivos estáticos
    ├── index.html      # Estrutura da página
    ├── styles.css      # Design e animações
    └── app.js          # Lógica do chat e chamadas API
```
