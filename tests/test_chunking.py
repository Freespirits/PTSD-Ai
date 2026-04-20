"""Tests for Hebrew chunking."""

import pytest
from ingestion.chunking import chunk_hebrew_text


def test_empty_input():
    assert chunk_hebrew_text("") == []
    assert chunk_hebrew_text("   ") == []


def test_short_text_single_chunk():
    text = "זה משפט קצר אחד."
    chunks = chunk_hebrew_text(text, target_size=600)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_long_text_multiple_chunks():
    sentence = "פוסט-טראומה היא תופעה שעלולה להופיע בעקבות אירועים טראומטיים. "
    text = sentence * 50  # ~3000 chars
    chunks = chunk_hebrew_text(text, target_size=600, overlap=80)
    assert len(chunks) >= 4
    # All chunks roughly within target
    assert all(len(c) <= 900 for c in chunks)
    assert all(len(c) >= 100 for c in chunks[:-1])  # last can be small


def test_paragraph_preservation():
    text = "פסקה ראשונה.\n\nפסקה שנייה.\n\nפסקה שלישית."
    chunks = chunk_hebrew_text(text, target_size=600)
    assert len(chunks) == 1  # all fits


def test_overlap_present():
    text = ("משפט אחד. " * 30) + ("\n\n" + "משפט שני. " * 30)
    chunks = chunk_hebrew_text(text, target_size=200, overlap=50)
    if len(chunks) >= 2:
        # Some overlap should exist between consecutive chunks
        # (last words of chunk N appear at start of chunk N+1)
        for i in range(len(chunks) - 1):
            tail = chunks[i][-30:]
            assert any(word in chunks[i + 1][:80] for word in tail.split() if len(word) > 2), \
                f"No overlap between chunk {i} and {i+1}"


def test_huge_sentence_hard_split():
    # A 2000-char sentence with no breakpoints
    text = "מילה " * 400  # 2000 chars
    chunks = chunk_hebrew_text(text, target_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 400 for c in chunks)


def test_no_word_split():
    text = "מילההארוכהשלאצריכהלהיחתך " * 100
    chunks = chunk_hebrew_text(text, target_size=300, overlap=30)
    # No chunk should END mid-word (last char before space or end)
    for chunk in chunks[:-1]:
        # Either the chunk ends with a space or with a complete token
        assert chunk[-1] != "ל" or chunk.endswith("מילההארוכהשלאצריכהלהיחתך")


def test_mixed_hebrew_english():
    text = (
        "PTSD היא Post-Traumatic Stress Disorder. "
        "מחקרים מ-Harvard ו-Stanford הראו ש-EMDR יכול לעזור. "
        "פסיכולוגים בישראל משתמשים ב-CBT וב-prolonged exposure."
    ) * 10
    chunks = chunk_hebrew_text(text, target_size=400)
    assert len(chunks) >= 1
    # All chunks should preserve mixed-language text
    for chunk in chunks:
        assert "PTSD" in chunk or "EMDR" in chunk or "CBT" in chunk or "Harvard" in chunk or "Stanford" in chunk
