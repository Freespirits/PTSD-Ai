"""Hebrew-aware text chunking.

Strategy:
1. Try to split on natural sentence boundaries (Hebrew punctuation: . ! ? : ;).
2. Respect paragraph breaks.
3. Maintain target chunk size with small overlap for context preservation.
4. Avoid splitting mid-word.
"""

from __future__ import annotations

import re

# Hebrew + Latin sentence terminators
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[\u0590-\u05FFA-Z])")
PARAGRAPH_RE = re.compile(r"\n\s*\n")


def chunk_hebrew_text(
    text: str,
    target_size: int = 600,
    overlap: int = 80,
    min_size: int = 200,
) -> list[str]:
    """Split text into chunks of roughly `target_size` chars with `overlap`.

    Args:
        text: Input text (Hebrew, Latin, mixed).
        target_size: Desired chunk size in chars (~150 tokens).
        overlap: Chars from end of one chunk that bleed into the next.
        min_size: Don't emit chunks smaller than this (merges with previous).
    """
    text = _clean(text)
    if not text:
        return []

    # First split into paragraphs to preserve structure
    paragraphs = [p.strip() for p in PARAGRAPH_RE.split(text) if p.strip()]

    # Then split paragraphs into sentences
    sentences: list[str] = []
    for para in paragraphs:
        for sent in _split_sentences(para):
            if sent.strip():
                sentences.append(sent.strip())

    # Greedily build chunks
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent)

        # If a single sentence is huge, hard-split it
        if sent_len > target_size * 1.5:
            if current:
                chunks.append(" ".join(current))
                current = _carry_overlap(current, overlap)
                current_len = sum(len(s) + 1 for s in current)
            chunks.extend(_hard_split(sent, target_size, overlap))
            current = []
            current_len = 0
            continue

        if current_len + sent_len + 1 > target_size and current_len >= min_size:
            chunks.append(" ".join(current))
            current = _carry_overlap(current, overlap)
            current_len = sum(len(s) + 1 for s in current)

        current.append(sent)
        current_len += sent_len + 1

    if current:
        last = " ".join(current)
        if chunks and len(last) < min_size:
            # Merge tiny tail into previous chunk
            chunks[-1] = chunks[-1] + " " + last
        else:
            chunks.append(last)

    return chunks


def _split_sentences(text: str) -> list[str]:
    parts = SENTENCE_END_RE.split(text)
    # Fallback: if no clean splits, return whole text
    return parts if len(parts) > 1 else [text]


def _carry_overlap(sentences: list[str], overlap: int) -> list[str]:
    """Take the trailing sentences whose total length is around `overlap`."""
    if not sentences or overlap <= 0:
        return []
    carry: list[str] = []
    total = 0
    for sent in reversed(sentences):
        if total + len(sent) > overlap and carry:
            break
        carry.insert(0, sent)
        total += len(sent) + 1
    return carry


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    """Last-resort fixed-size split, avoiding breaking inside a word."""
    chunks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + size, n)
        # Walk back to nearest whitespace
        if end < n:
            ws = text.rfind(" ", i, end)
            if ws > i + size // 2:
                end = ws
        chunks.append(text[i:end].strip())
        i = max(end - overlap, end)
    return chunks


def _clean(text: str) -> str:
    # Normalize whitespace, strip control chars
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
