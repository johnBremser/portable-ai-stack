# =============================================================================
# Processamento de anexos para chat → Ollama (texto inline, imagens base64, PDF)
# PDF: texto com pypdf + PyMuPDF; páginas como imagem só via PyMuPDF (sem Poppler).
# =============================================================================

from __future__ import annotations

import base64
import io
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

from PIL import Image
from pypdf import PdfReader

# --- Limites (ajustáveis) ---
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_TEXT_CHARS = 80_000
MIN_PDF_TEXT_CHARS = 200
MAX_PDF_PAGES_AS_IMAGE = 5
MAX_IMAGE_EDGE_PX = 2048

TEXT_EXTENSIONS = frozenset({
    ".txt", ".csv", ".tsv", ".json", ".jsonl", ".ndjson",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte",
    ".php", ".phtml", ".md", ".markdown", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".env", ".properties",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".py", ".pyw", ".rb", ".go", ".rs", ".java", ".kt", ".c", ".h",
    ".cpp", ".hpp", ".cs", ".swift", ".scala", ".r", ".sql", ".graphql",
    ".css", ".scss", ".less", ".html", ".htm", ".svg",
    ".log", ".gitignore", ".dockerignore", ".editorconfig",
})

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
IMAGE_MIME_PREFIX = "image/"

TEXT_APPLICATION_TYPES = frozenset({
    "application/json",
    "application/javascript",
    "application/xml",
    "application/x-yaml",
    "application/yaml",
    "application/sql",
    "application/x-httpd-php",
    "application/x-sh",
    "application/ecmascript",
})


@dataclass
class AttachmentOutcome:
    """Resultado do processamento de um arquivo anexo."""

    history_tag: str
    extra_content: str
    images: list[str]
    #: Para PDF: comprimento do texto extraído (sem espaços); None nos outros tipos.
    pdf_extracted_non_ws: Optional[int] = None


class AttachmentError(Exception):
    """Erro de validação ou processamento (mapear para HTTP 415/422)."""

    pass


def _ext(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _normalize_mime(mime: Optional[str]) -> str:
    if not mime:
        return ""
    return mime.split(";")[0].strip().lower()


def _is_probably_text(ext: str, mime: str) -> bool:
    if f".{ext}" in TEXT_EXTENSIONS:
        return True
    m = _normalize_mime(mime)
    if m.startswith("text/"):
        return True
    if m in TEXT_APPLICATION_TYPES:
        return True
    return False


def _is_probably_image(ext: str, mime: str) -> bool:
    if f".{ext}" in IMAGE_EXTENSIONS:
        return True
    m = _normalize_mime(mime)
    return bool(m.startswith(IMAGE_MIME_PREFIX))


def _is_pdf(ext: str, mime: str) -> bool:
    return ext == "pdf" or _normalize_mime(mime) == "application/pdf"


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _non_ws_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _truncate_text(text: str, filename: str) -> str:
    if len(text) <= MAX_TEXT_CHARS:
        return text
    head = text[: MAX_TEXT_CHARS // 2]
    tail = text[-MAX_TEXT_CHARS // 2 :]
    return (
        f"{head}\n\n[… conteúdo omitido …]\n\n{tail}\n\n"
        f"[AVISO: arquivo truncado para ~{MAX_TEXT_CHARS} caracteres — {filename}]"
    )


def _pil_to_png_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    if img.mode == "RGBA":
        pass
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.save(buf, format="PNG", optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _resize_if_large(img: Image.Image) -> Image.Image:
    w, h = img.size
    m = max(w, h)
    if m <= MAX_IMAGE_EDGE_PX:
        return img
    scale = MAX_IMAGE_EDGE_PX / m
    nw, nh = int(w * scale), int(h * scale)
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def _process_image(filename: str, data: bytes) -> AttachmentOutcome:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise AttachmentError(f"Imagem inválida ou corrompida: {e}") from e
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    img = _resize_if_large(img)
    b64 = _pil_to_png_base64(img)
    return AttachmentOutcome(
        history_tag="imagem",
        extra_content="",
        images=[b64],
    )


def _process_text_file(filename: str, data: bytes) -> AttachmentOutcome:
    body = _decode_text(data)
    body = _truncate_text(body, filename)
    block = f"--- arquivo: {filename} ---\n{body}\n--- fim do arquivo ---"
    return AttachmentOutcome(
        history_tag="texto",
        extra_content=block,
        images=[],
    )


def _extract_pdf_text(data: bytes) -> str:
    pypdf_parts: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            pypdf_parts.append(t)
    except Exception:
        pass
    pypdf_text = "\n".join(pypdf_parts).strip()

    mu_text = ""
    blocks_text = ""
    try:
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        try:
            mu_parts: list[str] = []
            blk_parts: list[str] = []
            for i in range(doc.page_count):
                page = doc.load_page(i)
                try:
                    mu_parts.append(page.get_text() or "")
                except Exception:
                    mu_parts.append("")
                try:
                    for b in page.get_text("blocks") or []:
                        if isinstance(b, (tuple, list)) and len(b) > 4 and isinstance(b[4], str):
                            frag = (b[4] or "").strip()
                            if frag:
                                blk_parts.append(frag)
                except Exception:
                    pass
            mu_text = "\n".join(mu_parts).strip()
            blocks_text = "\n".join(blk_parts).strip()
        finally:
            doc.close()
    except ImportError:
        pass
    except Exception:
        pass

    best = pypdf_text
    for cand in (mu_text, blocks_text):
        if _non_ws_len(cand) > _non_ws_len(best):
            best = cand
    return best


def _pdf_pages_as_images(
    data: bytes,
    filename: str,
    *,
    pdf_extracted_non_ws: int,
) -> AttachmentOutcome:
    """Rasteriza primeiras páginas do PDF com PyMuPDF apenas (não usa Poppler/pdf2image)."""
    try:
        import fitz
    except ImportError as e:
        raise AttachmentError(
            "O pacote PyMuPDF é necessário para PDF escaneado ou com pouco texto. "
            "No ambiente do backend: pip install pymupdf"
        ) from e

    doc = None
    pages: list[Image.Image] = []
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        if doc.page_count < 1:
            raise AttachmentError("O PDF não tem páginas renderizáveis.")

        n = min(doc.page_count, MAX_PDF_PAGES_AS_IMAGE)
        for i in range(n):
            page = doc.load_page(i)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pages.append(Image.open(io.BytesIO(pix.tobytes("png"))))
    except AttachmentError:
        raise
    except Exception as e:
        raise AttachmentError(
            f"Não foi possível converter o PDF «{filename}» em imagens. "
            "Verifique se o ficheiro é um PDF válido, não está corrompido e não tem palavra-passe. "
            f"Detalhe: {e}"
        ) from e
    finally:
        if doc is not None:
            doc.close()

    if not pages:
        raise AttachmentError(
            "PDF sem páginas renderizáveis ou texto extraível. Tente outro arquivo."
        )

    b64_list: list[str] = []
    for pil in pages:
        pil = _resize_if_large(pil.convert("RGB"))
        b64_list.append(_pil_to_png_base64(pil))

    intro = (
        f"O PDF «{filename}» não tinha texto extraível (ou pouco texto). "
        f"Seguem as primeiras {len(b64_list)} página(s) como imagem(ns), em ordem. "
        "Analise o conteúdo visual."
    )
    return AttachmentOutcome(
        history_tag="pdf-imagem",
        extra_content=intro,
        images=b64_list,
        pdf_extracted_non_ws=pdf_extracted_non_ws,
    )


def _process_pdf(filename: str, data: bytes) -> AttachmentOutcome:
    text = _extract_pdf_text(data)
    n = _non_ws_len(text)
    if n >= MIN_PDF_TEXT_CHARS:
        body = _truncate_text(text, filename)
        block = f"--- arquivo: {filename} (texto extraído do PDF) ---\n{body}\n--- fim ---"
        return AttachmentOutcome(
            history_tag="pdf-texto",
            extra_content=block,
            images=[],
            pdf_extracted_non_ws=n,
        )
    logger.info(
        "PDF %r: texto extraído ≈ %d caracteres não-brancos (mínimo só-texto=%d) → rasterizar páginas",
        filename,
        n,
        MIN_PDF_TEXT_CHARS,
    )
    return _pdf_pages_as_images(data, filename, pdf_extracted_non_ws=n)


def process_attachment(filename: str, content_type: Optional[str], data: bytes) -> AttachmentOutcome:
    """
    Classifica o arquivo, aplica limites e devolve conteúdo para `content` e/ou `images` do Ollama.
    Levanta AttachmentError para respostas 415/422.
    """
    if not data:
        raise AttachmentError("Arquivo vazio.")

    if len(data) > MAX_FILE_BYTES:
        raise AttachmentError(
            f"Arquivo excede o limite de {MAX_FILE_BYTES // (1024 * 1024)} MB."
        )

    ext = _ext(filename)
    mime = _normalize_mime(content_type)

    if _is_pdf(ext, mime):
        return _process_pdf(filename, data)

    if _is_probably_image(ext, mime):
        return _process_image(filename, data)

    if _is_probably_text(ext, mime):
        return _process_text_file(filename, data)

    raise AttachmentError(
        f"Tipo não suportado ({mime or 'desconhecido'}, .{ext or '?'}). "
        "Use imagem (png, jpeg, webp, gif), PDF ou arquivo de texto/código (csv, json, md, etc.)."
    )


def compose_user_message(user_text: str, outcome: AttachmentOutcome) -> str:
    """Junta a mensagem do usuário com blocos de texto do anexo (sem imagens)."""
    msg = (user_text or "").strip()
    if not msg:
        msg = "Analise o anexo."
    extra = (outcome.extra_content or "").strip()
    if not extra:
        return msg
    return f"{extra}\n\n---\n\n{msg}"
