"""Document loaders. Routes by extension to the right parser."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_document(path: Path) -> str:
    """Extract plain text from a document. Returns empty string on failure."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)
    if suffix in (".md", ".txt"):
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix in (".html", ".htm"):
        return _load_html(path)

    logger.warning("Unsupported file type: %s", suffix)
    return ""


def _load_pdf(path: Path) -> str:
    """Use pdfplumber for better Hebrew RTL support than pypdf."""
    try:
        import pdfplumber
        text_parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t.strip():
                    text_parts.append(t)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.exception("pdfplumber failed for %s, falling back to pypdf: %s", path, e)
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            return "\n\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e2:
            logger.exception("pypdf also failed for %s: %s", path, e2)
            return ""


def _load_docx(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        logger.exception("docx load failed for %s: %s", path, e)
        return ""


def _load_html(path: Path) -> str:
    try:
        from bs4 import BeautifulSoup
        html = path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        # Strip scripts/styles
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n")
    except Exception as e:
        logger.exception("html load failed for %s: %s", path, e)
        return ""
