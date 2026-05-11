# =============================================================================
# Backend — API REST para chat com LLM local via Ollama
# Stack: FastAPI + httpx + SSE (Server-Sent Events para streaming)
#
# Endpoints:
#   POST /chat          — chat normal via SSE streaming
#   POST /chat/upload   — chat com arquivo via SSE streaming
#   GET  /models        — lista modelos disponíveis no Ollama
#   GET  /health        — status do servidor e do Ollama (+ pdf_raster, attachments_py)
#   GET  /stack-info    — diagnóstico de versão/caminho (sem cache)
#   DELETE /session/{id} — limpa histórico de uma sessão
# =============================================================================

import os
import time
import uuid
import json
import httpx
import asyncio
import logging
import sqlite3
import getpass
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError

import attachments
from attachments import AttachmentError, AttachmentOutcome, compose_user_message, process_attachment

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

# Para Ollama use: "http://localhost:11434/v1"
# Para LM Studio use: "http://localhost:1234/v1"
LLM_BASE_URL    = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
DEFAULT_MODEL   = os.environ.get("DEFAULT_MODEL", "gemma4:custom")

MAX_HISTORY     = 20    # máximo de turnos por sessão (evita context overflow)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Configuração do Banco de Dados (Portable)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "sessions.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
    # Tabela Unificada: id, título, usuário, JSON das mensagens e datas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            user TEXT,
            messages_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Identificação do Usuário da Máquina
def get_machine_user():
    try:
        return getpass.getuser()
    except:
        return "portable_user"

# Armazenamento em memória das sessões ativas (cache)
sessions: dict[str, list[dict]] = {}


# =============================================================================
# LIFESPAN — verifica conexão com Ollama na inicialização
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando Banco de Dados Portable...")
    init_db()
    logger.info(f"Iniciando API — Usuário: {get_machine_user()}")
    logger.info(f"Conectando em {LLM_BASE_URL}...")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{LLM_BASE_URL}/models")
            if resp.status_code == 200:
                data = resp.json().get("data") or []
                modelos = [m["id"] for m in data if "id" in m]
                logger.info(f"LLM Conectado. Modelos disponíveis: {modelos}")
            else:
                logger.warning(f"Resposta inesperada de {LLM_BASE_URL}/models: {resp.status_code}")
    except Exception as e:
        logger.warning(f"LLM não respondeu na inicialização: {e}")
    logger.info(
        "Anexos/PDF: rasterização só com PyMuPDF (sem Poppler). Módulo: %s",
        getattr(attachments, "__file__", "?"),
    )
    yield
    logger.info("API encerrada.")


# =============================================================================
# APLICAÇÃO
# =============================================================================

app = FastAPI(
    title="Local LLM Chat API",
    description="API para chat com modelos locais via Ollama",
    version="1.0.1",
    lifespan=lifespan,
)

# Permite requisições de qualquer origem (necessário para frontend separado)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# SCHEMAS
# =============================================================================

class ChatRequest(BaseModel):
    message: str                          = Field(..., min_length=1)
    session_id: Optional[str]            = Field(default=None)
    model: str                            = Field(default=DEFAULT_MODEL)
    system_prompt: Optional[str]         = Field(default=None)
    temperature: float                    = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int                       = Field(default=2048, ge=64, le=65536)
    top_p: float                          = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int                            = Field(default=40, ge=0, le=100000)
    # Ollama: parâmetro de topo em /api/chat (não vai em options). False = só resposta final.
    think: bool                           = Field(default=False)

class AttachmentProcessInfo(BaseModel):
    """Como o anexo foi enviado ao Ollama (só em /chat/upload)."""

    mode: str
    summary: str
    history_tag: str
    text_chars: Optional[int] = None
    image_count: int = 0
    #: PDF: caracteres não-brancos obtidos na extração (antes de decidir texto vs imagem).
    extracted_non_ws: Optional[int] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    model: str
    tokens_used: Optional[int]
    timestamp: str
    attachment: Optional[AttachmentProcessInfo] = None


def _attachment_process_info(outcome: AttachmentOutcome) -> AttachmentProcessInfo:
    """Explica para cliente e logs.

    No Ollama POST /api/chat, mensagens multimodais usam o array **images** 
    Uma foto ou N páginas de PDF viram N strings base64 nesse mesmo array.
    """
    tag = outcome.history_tag
    n_img = len(outcome.images) if outcome.images else 0
    tchars = len(outcome.extra_content) if outcome.extra_content else 0
    ext_n = outcome.pdf_extracted_non_ws

    if tag == "pdf-texto":
        return AttachmentProcessInfo(
            mode="pdf_text",
            history_tag=tag,
            text_chars=tchars,
            image_count=0,
            extracted_non_ws=ext_n,
            summary=(
                "Texto extraído do PDF (pypdf + PyMuPDF) e enviado no campo content da mensagem; "
                "nenhuma imagem/base64 no array images."
            ),
        )
    if tag == "pdf-imagem":
        return AttachmentProcessInfo(
            mode="pdf_images",
            history_tag=tag,
            text_chars=tchars,
            image_count=n_img,
            extracted_non_ws=ext_n,
            summary=(
                f"Pouco texto extraível na extração (≈{ext_n if ext_n is not None else '?'} caracteres "
                f"não-brancos, abaixo do limiar); {n_img} página(s) renderizada(s) com PyMuPDF como PNG "
                "no array \"images\" do Ollama (modelo com visão)."
            ),
        )
    if tag == "imagem":
        return AttachmentProcessInfo(
            mode="image",
            history_tag=tag,
            text_chars=0,
            image_count=n_img,
            summary=(
                "Imagem convertida para PNG — enviada em base64 no array \"images\" da mensagem "
                "user no /api/chat do Ollama; só a pergunta vai no \"content\"."
            ),
        )
    if tag == "texto":
        return AttachmentProcessInfo(
            mode="text_file",
            history_tag=tag,
            text_chars=tchars,
            image_count=0,
            summary="Arquivo de texto/código lido como UTF-8 e enviado no campo content.",
        )
    return AttachmentProcessInfo(
        mode="unknown",
        history_tag=tag,
        text_chars=tchars,
        image_count=n_img,
        summary=f"Tag interna {tag!r}; {n_img} imagem(ns).",
    )


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def get_or_create_session(session_id: Optional[str]) -> str:
    """Retorna o session_id existente ou cria um novo."""
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = []
        logger.info(f"Nova sessão criada: {session_id}")
    return session_id


def build_messages(
    session_id: str,
    user_message: str,
    system_prompt: Optional[str],
    images: Optional[list[str]] = None,
) -> list[dict]:
    """Monta a lista de mensagens com histórico + nova mensagem (Padrão OpenAI)."""
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    history = sessions[session_id][-MAX_HISTORY:]
    messages.extend(history)

    # Conteúdo multimodal ou texto simples
    if images:
        content = [{"type": "text", "text": user_message}]
        for b64 in images:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"}
            })
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_message})

    return messages


def update_history(session_id: str, user_message: str, assistant_reply: str):
    """Salva no banco de dados serializando o histórico em JSON."""
    user = get_machine_user()
    
    # Atualiza cache em memória
    if session_id not in sessions: sessions[session_id] = []
    sessions[session_id].append({"role": "user",      "content": user_message})
    sessions[session_id].append({"role": "assistant", "content": assistant_reply})
    
    messages_json = json.dumps(sessions[session_id])
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Verifica se já existe
    cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if not cursor.fetchone():
        # Título inteligente: Pega a primeira linha e trunca
        clean_title = user_message.split("\n")[0].strip()
        title = clean_title[:40] + ("..." if len(clean_title) > 40 else "")
        cursor.execute(
            "INSERT INTO sessions (id, title, user, messages_json) VALUES (?, ?, ?, ?)",
            (session_id, title, user, messages_json)
        )
    else:
        cursor.execute(
            "UPDATE sessions SET messages_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (messages_json, session_id)
        )
    
    conn.commit()
    conn.close()


# Helper functions removed or merged into endpoints


async def _stream_llm_events(
    payload: dict,
    session_id: str,
    user_message: str,
    *,
    history_user_msg: Optional[str] = None,
    timeout: int = 120,
) -> AsyncGenerator[str, None]:
    """Chama LLM (Padrão OpenAI) com streaming e yield eventos SSE."""
    full_reply = ""
    full_think = ""
    in_think_block = False
    usage = {}
    start_time = time.perf_counter()
    first_token_time = None
    
    yield f"data: {json.dumps({'session_id': session_id, 'type': 'start'})}\n\n"
    logger.info(f"Enviando para Ollama: Modelo={payload.get('model')} | Mensagens={len(payload.get('messages', []))}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{LLM_BASE_URL}/chat/completions",
                json=payload,
            ) as response:
                if response.status_code != 200:
                    err = await response.aread()
                    yield f"data: {json.dumps({'type': 'error', 'detail': f'LLM Error {response.status_code}: {err.decode()}'})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        chunk = json.loads(data_str)
                        
                        # Captura usage (muitos providers enviam no último chunk ou num chunk dedicado)
                        usage = chunk.get("usage")
                        if usage:
                            # Se o chunk for só de usage, não tentamos processar escolhas
                            if not chunk.get("choices"):
                                continue

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                            
                        choice = choices[0]
                        delta = choice.get("delta", {})
                        
                        # Marca tempo do primeiro token
                        if first_token_time is None and (delta.get("content") or delta.get("reasoning_content")):
                            first_token_time = time.perf_counter()

                        # 1. Suporte a reasoning_content (DeepSeek)
                        think_tok = delta.get("reasoning_content") or ""
                        content_tok = delta.get("content") or ""

                        if think_tok:
                            full_think += think_tok
                            logger.info(f"Ollama [Thinking]: {think_tok}")
                            yield f"data: {json.dumps({'type': 'think', 'token': think_tok})}\n\n"
                        
                        if content_tok:
                            # 2. Heurística para tags <think> (Ollama/LM Studio em alguns modelos)
                            if "<think>" in content_tok:
                                in_think_block = True
                                parts = content_tok.split("<think>", 1)
                                if parts[0]:
                                    full_reply += parts[0]
                                    yield f"data: {json.dumps({'type': 'token', 'token': parts[0]})}\n\n"
                                content_tok = parts[1]
                            
                            if "</think>" in content_tok:
                                in_think_block = False
                                parts = content_tok.split("</think>", 1)
                                if parts[0]:
                                    full_think += parts[0]
                                    yield f"data: {json.dumps({'type': 'think', 'token': parts[0]})}\n\n"
                                content_tok = parts[1]

                            if in_think_block:
                                full_think += content_tok
                                logger.info(f"Ollama [Think-Tag]: {content_tok}")
                                yield f"data: {json.dumps({'type': 'think', 'token': content_tok})}\n\n"
                            elif content_tok:
                                full_reply += content_tok
                                logger.info(f"Ollama [Token]: {content_tok}")
                                yield f"data: {json.dumps({'type': 'token', 'token': content_tok})}\n\n"

                    except (json.JSONDecodeError, IndexError):
                        continue
    
        # Cálculos finais
        end_time = time.perf_counter()
        duration = end_time - start_time
        ttft = (first_token_time - start_time) if first_token_time else duration
        
        # Estimar tokens se o provider não mandou usage
        # (Muitos modelos locais ainda falham em mandar usage no stream OpenAI)
        tokens_estimate = int((len(full_reply) + len(full_think)) / 4) # Heurística simples: 4 caracteres/token
        tokens_used = usage.get("total_tokens") if usage else tokens_estimate
        tps = tokens_used / (duration - ttft) if (duration - ttft) > 0 else 0

        # Salva histórico
        hist_msg = history_user_msg if history_user_msg is not None else user_message
        update_history(session_id, hist_msg, full_reply)
        
        done_data = {
            "type": "done",
            "session_id": session_id,
            "tokens_used": tokens_used,
            "duration": round(duration, 2),
            "ttft": round(ttft, 2),
            "tps": round(tps, 2)
        }
        yield f"data: {json.dumps(done_data)}\n\n"

    except asyncio.CancelledError:
        logger.info(f"Stream interrompido pelo cliente (session: {session_id})")
        raise
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"


def _sse_response():
    """Headers padrão para SSE."""
    return {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check():
    """Verifica se a API e o Ollama estão operacionais."""
    llm_ok = False
    modelos   = []

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp   = await client.get(f"{LLM_BASE_URL}/models")
            data = resp.json().get("data") or []
            modelos = [m["id"] for m in data if "id" in m]
            llm_ok = True
    except Exception as e:
        logger.warning(f"Health check — LLM indisponível: {e}")

    payload = {
        "api":              "online",
        "ollama":           "online" if llm_ok else "offline",
        "models":           modelos,
        "sessions_active":  len(sessions),
        "timestamp":        datetime.now().isoformat(),
        "api_version":      app.version,
        "provider_url":     LLM_BASE_URL
    }
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@app.get("/stack-info")
async def stack_info():
    """Diagnóstico: versão e caminho do módulo attachments (evita confusão com cache ou processo antigo)."""
    return JSONResponse(
        content={
            "api_version":    app.version,
            "pdf_raster":     "pymupdf",
            "attachments_py": getattr(attachments, "__file__", None),
            "cwd":            os.getcwd(),
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@app.get("/models")
async def list_models():
    """Lista todos os modelos disponíveis no LLM local."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{LLM_BASE_URL}/models")
            data = resp.json().get("data", [])
            return {
                "models": [
                    {
                        "name":     m["id"],
                        "size_gb":  0,  # OpenAI API não fornece tamanho via /models
                        "modified": "",
                    }
                    for m in data
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM indisponível: {e}")


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Envia uma mensagem e retorna a resposta em streaming (SSE).
    Padronizado para API OpenAI.
    """
    session_id = get_or_create_session(req.session_id)
    messages   = build_messages(session_id, req.message, req.system_prompt)
    
    payload = {
        "model": req.model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "top_p": req.top_p,
        # top_k não é padrão OpenAI mas muitos providers locais aceitam
        "extra_body": {"top_k": req.top_k} if req.top_k != 40 else {}
    }

    return StreamingResponse(
        _stream_llm_events(payload, session_id, req.message, timeout=120),
        media_type="text/event-stream",
        headers=_sse_response(),
    )


# _parse_upload_form removed as logic was simplified in chat_upload


@app.post("/chat/upload")
async def chat_upload(
    file: UploadFile = File(...),
    message: str = Form(""),
    session_id: str = Form(""),
    model: str = Form(DEFAULT_MODEL),
    system_prompt: str = Form(""),
    temperature: str = Form("0.7"),
    max_tokens: str = Form("2048"),
    top_p: str = Form("0.9"),
    top_k: str = Form("40"),
    think: str = Form("false"),
):
    """
    Envia mensagem com um anexo (imagem, texto/código, PDF).
    multipart/form-data: campo `file` + mesmos parâmetros do /chat como Form fields.
    Resposta em streaming SSE compatível com OpenAI.
    """
    # Parsing manual simplificado para evitar validação complexa do Pydantic em Form
    try:
        t = float(temperature)
        mt = int(max_tokens)
        tp = float(top_p)
        tk = int(top_k)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Parâmetro numérico inválido: {e}")

    data = await file.read()
    fname = os.path.basename(file.filename or "upload") or "upload"

    try:
        outcome = process_attachment(fname, file.content_type, data)
    except AttachmentError as e:
        raise HTTPException(status_code=415, detail=str(e)) from e

    full_user_msg = compose_user_message(message, outcome)
    session_id = get_or_create_session(session_id)
    
    messages = build_messages(
        session_id,
        full_user_msg,
        system_prompt or None,
        images=outcome.images if outcome.images else None,
    )
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": t,
        "max_tokens": mt,
        "top_p": tp,
    }

    # Mensagem do histórico inclui metadados do anexo
    history_user = f"{message}\n[Anexo: {fname}]"

    return StreamingResponse(
        _stream_llm_events(
            payload, session_id, message,
            history_user_msg=history_user,
            timeout=300,
        ),
        media_type="text/event-stream",
        headers=_sse_response(),
    )


@app.get("/sessions")
async def list_all_sessions():
    """Lista todas as conversas salvas no banco de dados para o menu lateral."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, user, created_at FROM sessions ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return {"sessions": [dict(r) for r in rows]}


@app.get("/session/{session_id}")
async def get_session_history(session_id: str):
    """Retorna o histórico de mensagens, carregando do JSON no DB."""
    if session_id in sessions and sessions[session_id]:
        return {
            "session_id": session_id,
            "messages":   sessions[session_id],
            "total":      len(sessions[session_id]),
        }
    
    # Busca no Banco de Dados
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT messages_json FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    
    messages = json.loads(row["messages_json"])
    sessions[session_id] = messages # Sincroniza cache
    
    return {
        "session_id": session_id,
        "messages":   messages,
        "total":      len(messages),
    }


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Apaga permanentemente uma sessão do banco de dados."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    
    if session_id in sessions:
        del sessions[session_id]
    
    logger.info(f"Sessão deletada: {session_id}")
    return {"message": "Conversa apagada com sucesso.", "session_id": session_id}


@app.delete("/sessions")
async def clear_all_sessions():
    """Limpa todas as sessões do banco de dados (CUIDADO!)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()
    sessions.clear()
    return {"message": "Todas as conversas foram apagadas."}


if __name__ == "__main__":
    import uvicorn

    # Bytecode em disco: apagar __pycache__ (clean_cache.bat) ou arrancar com: python -B api.py
    _port = int(os.environ.get("PORT", "8500"))
    uvicorn.run("api:app", host="0.0.0.0", port=_port, reload=True)
