# =============================================================================
# Backend â€” API REST para chat com LLM local via Ollama
# Stack: FastAPI + httpx + SSE (Server-Sent Events para streaming)
#
# Endpoints:
#   POST /chat          â€” chat normal via SSE streaming
#   POST /chat/upload   â€” chat com arquivo via SSE streaming
#   GET  /models        â€” lista modelos disponÃ­veis no Ollama
#   GET  /health        â€” status do servidor e do Ollama (+ pdf_raster, attachments_py)
#   GET  /stack-info    â€” diagnÃ³stico de versÃ£o/caminho (sem cache)
#   GET  /sessions      â€” lista todas as conversas salvas
#   GET  /session/{id}  â€” carrega histÃ³rico de uma sessÃ£o (cache ou DB)
#   DELETE /session/{id} â€” apaga uma sessÃ£o do banco
#   DELETE /sessions     â€” apaga todas as sessÃµes
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
import re
from urllib.parse import quote
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

import attachments
from attachments import AttachmentError, AttachmentOutcome, compose_user_message, process_attachment

# =============================================================================
# CONFIGURAÃ‡ÃƒO
# =============================================================================

# Para Ollama use: "http://localhost:11434/v1"
# Para LM Studio use: "http://localhost:1234/v1"
# Para Llama.cpp use: "http://localhost:8080/v1"
LLM_BASE_URL    = os.environ.get("LLM_BASE_URL", "http://localhost:8080/v1")
DEFAULT_MODEL   = os.environ.get("DEFAULT_MODEL", "qwen3.5:9b")
MAX_HISTORY     = 20    # mÃ¡ximo de turnos por sessÃ£o (evita context overflow)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "data", "sessions.db")
ATTACHMENTS_DIR = os.path.join(BASE_DIR, "data", "attachments")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Cache em memÃ³ria das sessÃµes ativas {session_id: [messages]}
sessions: dict[str, list[dict]] = {}


# =============================================================================
# BANCO DE DADOS (SQLite)
# =============================================================================

def get_machine_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "portable_user"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
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
    try:
        cursor.execute("ALTER TABLE attachments RENAME TO session_attachments")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_attachments (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT,
            relative_path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_settings (
            session_id TEXT PRIMARY KEY,
            system_prompt TEXT,
            temperature REAL,
            top_p REAL,
            top_k INTEGER,
            max_tokens INTEGER,
            think_enabled BOOLEAN,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_attachments_session_id ON session_attachments(session_id)")
    conn.commit()
    conn.close()


# =============================================================================
# LIFESPAN â€” verifica conexÃ£o com Ollama na inicializaÃ§Ã£o
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando Banco de Dados...")
    init_db()
    logger.info(f"UsuÃ¡rio: {get_machine_user()} | DB: {DB_PATH}")
    logger.info(f"Iniciando API â€” Conectando em {LLM_BASE_URL}...")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{LLM_BASE_URL}/models")
            if resp.status_code == 200:
                modelos = [m["id"] for m in resp.json().get("data", [])]
                logger.info(f"LLM Conectado. Modelos disponÃ­veis: {modelos}")
            else:
                logger.warning(f"Resposta inesperada de {LLM_BASE_URL}/models: {resp.status_code}")
    except Exception as e:
        logger.warning(f"LLM nÃ£o respondeu na inicializaÃ§Ã£o: {e}")
    logger.info(
        "Anexos/PDF: rasterizaÃ§Ã£o sÃ³ com PyMuPDF (sem Poppler). MÃ³dulo: %s",
        getattr(attachments, "__file__", "?"),
    )
    yield
    logger.info("API encerrada.")


# =============================================================================
# APLICAÃ‡ÃƒO
# =============================================================================

app = FastAPI(
    title="Local LLM Chat API",
    description="API para chat com modelos locais via Ollama",
    version="1.0.1",
    lifespan=lifespan,
)

# Permite requisiÃ§Ãµes de qualquer origem (necessÃ¡rio para frontend separado)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
app.mount("/attachments", StaticFiles(directory=ATTACHMENTS_DIR), name="attachments")


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
    # Ollama: parÃ¢metro de topo em /api/chat (nÃ£o vai em options). False = sÃ³ resposta final.
    think: bool                           = Field(default=False)
    reuse_attachment_ids: list[str]       = Field(default_factory=list)

class AttachmentProcessInfo(BaseModel):
    """Como o anexo foi enviado ao Ollama (sÃ³ em /chat/upload)."""

    mode: str
    summary: str
    history_tag: str
    text_chars: Optional[int] = None
    image_count: int = 0
    #: PDF: caracteres nÃ£o-brancos obtidos na extraÃ§Ã£o (antes de decidir texto vs imagem).
    extracted_non_ws: Optional[int] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    model: str
    tokens_used: Optional[int]
    timestamp: str
    attachment: Optional[AttachmentProcessInfo] = None

class AppSettings(BaseModel):
    global_system_prompt: Optional[str] = ""
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 2048
    think_enabled: bool = False

class SessionSettings(BaseModel):
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    think_enabled: Optional[bool] = None


def _attachment_process_info(outcome: AttachmentOutcome) -> AttachmentProcessInfo:
    """Explica para cliente e logs.

    No Ollama POST /api/chat, mensagens multimodais usam o array **images** 
    Uma foto ou N pÃ¡ginas de PDF viram N strings base64 nesse mesmo array.
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
                "Texto extraÃ­do do PDF (pypdf + PyMuPDF) e enviado no campo content da mensagem; "
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
                f"Pouco texto extraÃ­vel na extraÃ§Ã£o (â‰ˆ{ext_n if ext_n is not None else '?'} caracteres "
                f"nÃ£o-brancos, abaixo do limiar); {n_img} pÃ¡gina(s) renderizada(s) com PyMuPDF como PNG "
                "no array \"images\" do Ollama (modelo com visÃ£o)."
            ),
        )
    if tag == "imagem":
        return AttachmentProcessInfo(
            mode="image",
            history_tag=tag,
            text_chars=0,
            image_count=n_img,
            summary=(
                "Imagem convertida para PNG â€” enviada em base64 no array \"images\" da mensagem "
                "user no /api/chat do Ollama; sÃ³ a pergunta vai no \"content\"."
            ),
        )
    if tag == "texto":
        return AttachmentProcessInfo(
            mode="text_file",
            history_tag=tag,
            text_chars=tchars,
            image_count=0,
            summary="Arquivo de texto/cÃ³digo lido como UTF-8 e enviado no campo content.",
        )
    return AttachmentProcessInfo(
        mode="unknown",
        history_tag=tag,
        text_chars=tchars,
        image_count=n_img,
        summary=f"Tag interna {tag!r}; {n_img} imagem(ns).",
    )


# =============================================================================
# FUNÃ‡Ã•ES AUXILIARES
# =============================================================================

def get_or_create_session(session_id: Optional[str]) -> str:
    """Retorna o session_id existente ou cria um novo.
    Se o session_id existe no DB mas nÃ£o no cache, recarrega do banco."""
    if session_id and session_id in sessions:
        return session_id

    if session_id:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT messages_json FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            sessions[session_id] = json.loads(row["messages_json"])
            logger.info(f"SessÃ£o restaurada do DB: {session_id}")
            return session_id

    session_id = str(uuid.uuid4())
    sessions[session_id] = []
    logger.info(f"Nova sessÃ£o criada: {session_id}")
    return session_id


def _sanitize_filename(filename: str) -> str:
    base = os.path.basename(filename or "arquivo")
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", base).strip("._")
    return clean or "arquivo"


def save_attachment_file(session_id: str, filename: str, mime_type: Optional[str], data: bytes) -> dict[str, str]:
    safe_name = _sanitize_filename(filename)
    attachment_id = str(uuid.uuid4())
    rel_path = os.path.join(session_id, f"{attachment_id}_{safe_name}")
    abs_path = os.path.join(ATTACHMENTS_DIR, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(data)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO session_attachments (id, session_id, filename, mime_type, relative_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (attachment_id, session_id, safe_name, (mime_type or "").strip(), rel_path.replace("\\", "/")),
    )
    conn.commit()
    conn.close()

    return {
        "id": attachment_id,
        "filename": safe_name,
        "mime_type": (mime_type or "").strip(),
        "relative_path": rel_path.replace("\\", "/"),
    }


def get_attachments_map(session_id: str, attachment_ids: list[str]) -> dict[str, dict[str, str]]:
    if not attachment_ids:
        return {}
    unique_ids = list(dict.fromkeys([x for x in attachment_ids if x]))
    placeholders = ",".join(["?"] * len(unique_ids))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT id, session_id, filename, mime_type, relative_path
        FROM session_attachments
        WHERE session_id = ? AND id IN ({placeholders})
        """,
        [session_id, *unique_ids],
    )
    rows = cursor.fetchall()
    conn.close()
    return {
        r["id"]: {
            "id": r["id"],
            "session_id": r["session_id"],
            "filename": r["filename"],
            "mime_type": r["mime_type"] or "",
            "relative_path": r["relative_path"],
        }
        for r in rows
    }


def build_attachment_client_payload(att: dict[str, str]) -> dict[str, str]:
    filename = att["filename"]
    low = filename.lower()
    mime = (att.get("mime_type") or "").lower()
    kind = "file"
    if mime.startswith("image/") or low.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        kind = "image"
    elif mime == "application/pdf" or low.endswith(".pdf"):
        kind = "pdf"
    return {
        "id": att["id"],
        "name": filename,
        "kind": kind,
        "url": "/attachments/" + quote(att["relative_path"]),
        "mime_type": att.get("mime_type") or "",
    }


def enrich_messages_with_attachments(session_id: str, history_messages: list[dict]) -> list[dict]:
    ids: list[str] = []
    for m in history_messages:
        ids.extend(m.get("attachment_ids", []) or [])
    att_map = get_attachments_map(session_id, ids)

    enriched: list[dict] = []
    for m in history_messages:
        msg = dict(m)
        att_ids = msg.get("attachment_ids", []) or []
        if att_ids:
            msg["attachments"] = [
                build_attachment_client_payload(att_map[aid]) for aid in att_ids if aid in att_map
            ]
        enriched.append(msg)
    return enriched


def build_reuse_outcome(session_id: str, reuse_attachment_ids: list[str]) -> tuple[str, list[str]]:
    if not reuse_attachment_ids:
        return "", []
    att_map = get_attachments_map(session_id, reuse_attachment_ids)
    if not att_map:
        return "", []

    text_parts: list[str] = []
    images: list[str] = []
    for aid in reuse_attachment_ids:
        att = att_map.get(aid)
        if not att:
            continue
        abs_path = os.path.join(ATTACHMENTS_DIR, att["relative_path"])
        if not os.path.isfile(abs_path):
            continue
        with open(abs_path, "rb") as f:
            data = f.read()
        outcome = process_attachment(att["filename"], att.get("mime_type") or None, data)
        if outcome.extra_content:
            text_parts.append(outcome.extra_content)
        if outcome.images:
            images.extend(outcome.images)

    if not text_parts and not images:
        return "", []
    extra_text = "\n\n".join(text_parts)
    return extra_text, images


def build_messages(
    session_id: str,
    user_message: str,
    system_prompt: Optional[str],
    images: Optional[list[str]] = None,
) -> list[dict]:
    """Monta a lista de mensagens com histÃ³rico + nova mensagem (PadrÃ£o OpenAI)."""
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    history = sessions[session_id][-MAX_HISTORY:]
    for h in history:
        # Sanitiza campos extras locais (attachment_ids, attachments, etc.) para API OpenAI compatÃ­vel
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    # ConteÃºdo multimodal ou texto simples
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


def update_history(
    session_id: str,
    user_message: str,
    assistant_reply: str,
    *,
    attachment_ids: Optional[list[str]] = None,
    session_settings: Optional[dict] = None,
):
    """Adiciona o par (user, assistant) ao histÃ³rico e persiste no SQLite."""
    user = get_machine_user()

    if session_id not in sessions:
        sessions[session_id] = []
    user_entry: dict[str, Any] = {"role": "user", "content": user_message}
    if attachment_ids:
        user_entry["attachment_ids"] = attachment_ids
    sessions[session_id].append(user_entry)
    sessions[session_id].append({"role": "assistant", "content": assistant_reply})

    messages_json = json.dumps(sessions[session_id])

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if not cursor.fetchone():
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
    
    # A persistÃªncia das configuraÃ§Ãµes da sessÃ£o agora Ã© feita exclusivamente
    # pelo endpoint POST /session/{session_id}/settings no frontend.

    conn.commit()
    conn.close()


# Helper functions removed or merged into endpoints


async def _stream_llm_events(
    payload: dict,
    session_id: str,
    user_message: str,
    *,
    history_user_msg: Optional[str] = None,
    history_attachment_ids: Optional[list[str]] = None,
    session_settings: Optional[dict] = None,
    timeout: int = 120,
    emit_think: bool = False,
) -> AsyncGenerator[str, None]:
    """Chama LLM (PadrÃ£o OpenAI) com streaming e yield eventos SSE.
    Se emit_think=False, tokens de raciocÃ­nio sÃ£o descartados silenciosamente."""
    full_reply = ""
    full_think = ""
    in_think_block = False
    usage = {}
    start_time = time.perf_counter()
    first_token_time = None
    
    yield f"data: {json.dumps({'session_id': session_id, 'type': 'start'})}\n\n"

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
                        
                        # Captura usage (muitos providers enviam no Ãºltimo chunk ou num chunk dedicado)
                        usage = chunk.get("usage")
                        if usage:
                            # Se o chunk for sÃ³ de usage, nÃ£o tentamos processar escolhas
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
                            if emit_think:
                                yield f"data: {json.dumps({'type': 'think', 'token': think_tok})}\n\n"
                        
                        if content_tok:
                            # 2. HeurÃ­stica para tags <think> (Ollama/LM Studio em alguns modelos)
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
                                    if emit_think:
                                        yield f"data: {json.dumps({'type': 'think', 'token': parts[0]})}\n\n"
                                content_tok = parts[1]

                            if in_think_block:
                                full_think += content_tok
                                if emit_think:
                                    yield f"data: {json.dumps({'type': 'think', 'token': content_tok})}\n\n"
                            elif content_tok:
                                full_reply += content_tok
                                yield f"data: {json.dumps({'type': 'token', 'token': content_tok})}\n\n"

                    except (json.JSONDecodeError, IndexError):
                        continue
    
        # CÃ¡lculos finais
        end_time = time.perf_counter()
        duration = end_time - start_time
        ttft = (first_token_time - start_time) if first_token_time else duration
        
        # Estimar tokens se o provider nÃ£o mandou usage
        # (Muitos modelos locais ainda falham em mandar usage no stream OpenAI)
        tokens_estimate = int((len(full_reply) + len(full_think)) / 4) # HeurÃ­stica simples: 4 caracteres/token
        completion_tokens = usage.get("completion_tokens") if usage else tokens_estimate
        total_tokens = usage.get("total_tokens") if usage else tokens_estimate
        
        tps = completion_tokens / (duration - ttft) if (duration - ttft) > 0 else 0

        # Salva histÃ³rico
        hist_msg = history_user_msg if history_user_msg is not None else user_message
        update_history(
            session_id, 
            hist_msg, 
            full_reply, 
            attachment_ids=history_attachment_ids,
            session_settings=session_settings
        )
        
        done_data = {
            "type": "done",
            "session_id": session_id,
            "tokens_used": completion_tokens,
            "total_tokens": total_tokens,
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
    """Headers padrÃ£o para SSE."""
    return {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check():
    """Verifica se a API e o Ollama estÃ£o operacionais."""
    llm_ok = False
    modelos   = []

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp   = await client.get(f"{LLM_BASE_URL}/models")
            data = resp.json().get("data", [])
            modelos = [m["id"] for m in data]
            llm_ok = True
    except Exception as e:
        logger.warning(f"Health check â€” LLM indisponÃ­vel: {e}")

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
    """DiagnÃ³stico: versÃ£o e caminho do mÃ³dulo attachments (evita confusÃ£o com cache ou processo antigo)."""
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
    """Lista todos os modelos disponÃ­veis no LLM local."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{LLM_BASE_URL}/models")
            data = resp.json().get("data", [])
            return {
                "models": [
                    {
                        "name":     m["id"],
                        "size_gb":  0,  # OpenAI API nÃ£o fornece tamanho via /models
                        "modified": "",
                    }
                    for m in data
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM indisponÃ­vel: {e}")


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Envia uma mensagem e retorna a resposta em streaming (SSE).
    Padronizado para API OpenAI.
    """
    session_id = get_or_create_session(req.session_id)
    reuse_ids = [x for x in (req.reuse_attachment_ids or []) if isinstance(x, str) and x.strip()]
    reuse_text, reuse_images = build_reuse_outcome(session_id, reuse_ids)
    base_msg = req.message
    if reuse_text:
        base_msg = f"{reuse_text}\n\n---\n\n{req.message}".strip()
    images = reuse_images or None
    messages = build_messages(session_id, base_msg, req.system_prompt, images=images)
    
    payload = {
        "model": req.model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "top_p": req.top_p,
        "top_k": req.top_k,
        "chat_template_kwargs": {"enable_thinking": req.think},
    }

    # Prepara configuraÃ§Ãµes para salvar na sessÃ£o
    session_params = {
        "system_prompt": req.system_prompt,
        "temperature": req.temperature,
        "top_p": req.top_p,
        "top_k": req.top_k,
        "max_tokens": req.max_tokens,
        "think_enabled": req.think
    }

    return StreamingResponse(
        _stream_llm_events(
            payload,
            session_id,
            req.message,
            history_user_msg=req.message,
            history_attachment_ids=reuse_ids,
            session_settings=session_params,
            timeout=120,
            emit_think=req.think,
        ),
        media_type="text/event-stream",
        headers=_sse_response(),
    )


@app.get("/settings")
async def get_settings():
    """Busca todas as configuraÃ§Ãµes globais do banco."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM app_settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


@app.post("/settings")
async def save_settings(settings: AppSettings):
    """Salva configuraÃ§Ãµes globais no banco."""
    conn = get_db()
    cursor = conn.cursor()
    data = settings.dict()
    for key, val in data.items():
        cursor.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(val))
        )
    conn.commit()
    conn.close()
    return {"message": "ConfiguraÃ§Ãµes salvas com sucesso."}


@app.post("/session/{session_id}/settings")
async def save_session_settings(session_id: str, settings: SessionSettings):
    """Salva configuraÃ§Ãµes de uma sessÃ£o especÃ­fica."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO session_settings (
            session_id, system_prompt, temperature, top_p, top_k, max_tokens, think_enabled
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            system_prompt=excluded.system_prompt,
            temperature=excluded.temperature,
            top_p=excluded.top_p,
            top_k=excluded.top_k,
            max_tokens=excluded.max_tokens,
            think_enabled=excluded.think_enabled
    """, (
        session_id,
        settings.system_prompt,
        settings.temperature,
        settings.top_p,
        settings.top_k,
        settings.max_tokens,
        settings.think_enabled
    ))
    conn.commit()
    conn.close()
    return {"message": "ConfiguraÃ§Ãµes da sessÃ£o salvas com sucesso."}



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
    reuse_attachment_ids: str = Form("[]"),
):
    """
    Envia mensagem com um anexo (imagem, texto/cÃ³digo, PDF).
    multipart/form-data: campo `file` + mesmos parÃ¢metros do /chat como Form fields.
    Resposta em streaming SSE compatÃ­vel com OpenAI.
    """
    try:
        t = float(temperature)
        mt = int(max_tokens)
        tp = float(top_p)
        tk = int(top_k)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"ParÃ¢metro numÃ©rico invÃ¡lido: {e}")

    think_bool = think.lower() in ("true", "1", "yes")
    try:
        reuse_ids_payload = json.loads(reuse_attachment_ids or "[]")
        if isinstance(reuse_ids_payload, list):
            reuse_ids = [str(x) for x in reuse_ids_payload if str(x).strip()]
        else:
            reuse_ids = []
    except json.JSONDecodeError:
        reuse_ids = []

    data = await file.read()
    fname = os.path.basename(file.filename or "upload") or "upload"

    try:
        outcome = process_attachment(fname, file.content_type, data)
    except AttachmentError as e:
        raise HTTPException(status_code=415, detail=str(e)) from e

    session_id = get_or_create_session(session_id)
    saved_attachment = save_attachment_file(session_id, fname, file.content_type, data)

    full_user_msg = compose_user_message(message, outcome)
    reuse_text, reuse_images = build_reuse_outcome(session_id, reuse_ids)
    if reuse_text:
        full_user_msg = f"{reuse_text}\n\n---\n\n{full_user_msg}".strip()

    all_images: list[str] = []
    if reuse_images:
        all_images.extend(reuse_images)
    if outcome.images:
        all_images.extend(outcome.images)
    
    messages = build_messages(
        session_id,
        full_user_msg,
        system_prompt or None,
        images=all_images if all_images else None,
    )
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": t,
        "max_tokens": mt,
        "top_p": tp,
        "top_k": tk,
        "chat_template_kwargs": {"enable_thinking": think_bool},
    }

    # Mensagem do histÃ³rico inclui metadados do anexo
    history_user = f"{message}\n[Anexo: {fname}]"
    history_attachment_ids = [*reuse_ids, saved_attachment["id"]]

    # Prepara configuraÃ§Ãµes para salvar na sessÃ£o
    session_params = {
        "system_prompt": system_prompt,
        "temperature": t,
        "top_p": tp,
        "top_k": tk,
        "max_tokens": mt,
        "think_enabled": think_bool
    }

    return StreamingResponse(
        _stream_llm_events(
            payload, session_id, message,
            history_user_msg=history_user,
            history_attachment_ids=history_attachment_ids,
            session_settings=session_params,
            timeout=300,
            emit_think=think_bool,
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
    """Retorna o histÃ³rico de mensagens, carregando do DB se necessÃ¡rio."""
    conn = get_db()
    cursor = conn.cursor()

    # Busca configuraÃ§Ãµes da sessÃ£o primeiro
    cursor.execute("SELECT * FROM session_settings WHERE session_id = ?", (session_id,))
    s_row = cursor.fetchone()
    session_settings_dict = dict(s_row) if s_row else None

    if session_id in sessions and sessions[session_id]:
        enriched = enrich_messages_with_attachments(session_id, sessions[session_id])
        conn.close()
        return {
            "session_id": session_id,
            "messages":   enriched,
            "total":      len(enriched),
            "settings":   session_settings_dict
        }

    cursor.execute("SELECT messages_json FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="SessÃ£o nÃ£o encontrada.")

    messages = json.loads(row["messages_json"])
    sessions[session_id] = messages
    enriched = enrich_messages_with_attachments(session_id, messages)

    return {
        "session_id": session_id,
        "messages":   enriched,
        "total":      len(enriched),
        "settings":   session_settings_dict
    }


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Apaga permanentemente uma sessÃ£o do banco de dados."""
    session_dir = os.path.join(ATTACHMENTS_DIR, session_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM session_attachments WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

    if os.path.isdir(session_dir):
        for root, dirs, files in os.walk(session_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(session_dir)

    if session_id in sessions:
        del sessions[session_id]

    logger.info(f"SessÃ£o deletada: {session_id}")
    return {"message": "Conversa apagada com sucesso.", "session_id": session_id}


@app.delete("/sessions")
async def clear_all_sessions():
    """Limpa todas as sessÃµes do banco de dados."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM session_attachments")
    cursor.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()
    if os.path.isdir(ATTACHMENTS_DIR):
        for root, dirs, files in os.walk(ATTACHMENTS_DIR, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
    sessions.clear()
    return {"message": "Todas as conversas foram apagadas."}


if __name__ == "__main__":
    import uvicorn

    # Bytecode em disco: apagar __pycache__ (clean_cache.bat) ou arrancar com: python -B api.py
    _port = int(os.environ.get("PORT", "8500"))
    uvicorn.run("api:app", host="0.0.0.0", port=_port, reload=True)


