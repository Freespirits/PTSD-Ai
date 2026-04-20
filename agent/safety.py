"""Safety layer: crisis detection, escalation, and content filtering.

This module is the first line of defense. Every user utterance is
analyzed BEFORE being passed to the LLM, and the LLM response is
checked AFTER generation for medical-advice-like content.

NEVER bypass this layer. NEVER cache its decisions across sessions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from agent.config import settings


class RiskLevel(str, Enum):
    NONE = "none"
    ELEVATED = "elevated"  # general distress, sad, anxious
    HIGH = "high"          # severe distress, hopelessness, severe symptoms
    CRISIS = "crisis"      # imminent danger - self/others


@dataclass
class SafetyAssessment:
    risk: RiskLevel
    triggered_phrases: list[str]
    suggested_response: str | None = None
    require_hotline_offer: bool = False


# -----------------------------------------------------------------------------
# Hebrew crisis lexicon
# Note: deliberately inclusive of slang and Israeli colloquialisms.
# Curated with mental-health awareness - don't make this list too narrow.
# -----------------------------------------------------------------------------

CRISIS_PATTERNS_HE: list[str] = [
    # Suicidal ideation
    r"\bלהתאבד\b",
    r"\bאתאבד\b",
    r"\bלשים סוף\b",
    r"\bלגמור עם זה\b",
    r"\bלא רוצה להיות (כאן|פה|בחיים)\b",
    r"\bלא רוצה לחיות\b",
    r"\bלא רוצה לקום (יותר|מחר|עוד)\b",
    r"\bלמות\b",
    r"\bהחיים שלי לא שווים\b",
    r"\bהעולם יהיה (יותר )?טוב בלעדיי\b",
    r"\bאיבוד צלם אנוש\b",
    # Self-harm
    r"\bלפגוע בעצמי\b",
    r"\bחותך את עצמי\b",
    r"\bלחתוך את עצמי\b",
    # Imminent danger to others
    r"\bלפגוע ב[א-ת]+\b",
    r"\bלהרוג\b",
    # Severe acute distress
    r"\bפלאשבק\b.*\b(עכשיו|אני שם|חוזר)\b",
    r"\bהתקף חרדה\b.*\b(עכשיו|לא נושם)\b",
    r"\bלא יכול לנשום\b",
]

ELEVATED_PATTERNS_HE: list[str] = [
    r"\bאני שבור\b",
    r"\bאני קרוס\b",
    r"\bלא יכול יותר\b",
    r"\bאין לי כוח\b",
    r"\bמרגיש ריק\b",
    r"\bחסר תקווה\b",
    r"\bאף אחד לא מבין\b",
    r"\bלבד\b",
    r"\bסיוטים\b",
    r"\bפלאשבקים?\b",
    r"\bמתעורר[ ת]? מבוהל\b",
]

# Patterns we look for in *agent output* to prevent medical advice
MEDICAL_ADVICE_PATTERNS_HE: list[str] = [
    r"\bקח (את )?(תרופ|כדור)",
    r"\bאני ממליץ ש?תיקח\b",
    r"\bמינון של\b",
    r"\b(טיפול|תרופה) (יעזור|נכונה) (לך|בשבילך)\b",
    r"\bהאבחנה שלך (היא|כנראה)\b",
    r"\bיש לך (PTSD|דיכאון|חרדה)\b",  # AI shouldn't diagnose
]


def assess_user_input(text: str) -> SafetyAssessment:
    """Analyze user utterance for risk level."""
    text_norm = _normalize_hebrew(text)

    crisis_hits = _find_matches(text_norm, CRISIS_PATTERNS_HE)
    if crisis_hits:
        return SafetyAssessment(
            risk=RiskLevel.CRISIS,
            triggered_phrases=crisis_hits,
            suggested_response=_build_crisis_response(),
            require_hotline_offer=True,
        )

    elevated_hits = _find_matches(text_norm, ELEVATED_PATTERNS_HE)
    if len(elevated_hits) >= 2:
        return SafetyAssessment(
            risk=RiskLevel.HIGH,
            triggered_phrases=elevated_hits,
            require_hotline_offer=True,
        )
    if elevated_hits:
        return SafetyAssessment(
            risk=RiskLevel.ELEVATED,
            triggered_phrases=elevated_hits,
        )

    return SafetyAssessment(risk=RiskLevel.NONE, triggered_phrases=[])


def filter_agent_output(text: str) -> tuple[str, list[str]]:
    """Check agent output for medical advice. Returns (cleaned_text, warnings)."""
    warnings: list[str] = []
    matches = _find_matches(_normalize_hebrew(text), MEDICAL_ADVICE_PATTERNS_HE)
    if matches:
        warnings.append(
            f"Output flagged for possible medical-advice content: {matches}"
        )
    return text, warnings


def _build_crisis_response() -> str:
    """Hebrew crisis response with escalation."""
    return (
        "אני שומע אותך, ומה שאתה מרגיש עכשיו זה אמיתי. "
        f"אני רוצה שתתקשר עכשיו לער\"ן בקו {settings.crisis_hotline_eran}, "
        f"או לנט\"ל - שמתמחים בטראומה צבאית - בקו {settings.crisis_hotline_natal}. "
        "שניהם דוברי עברית ופתוחים עכשיו, גם בלילה. "
        "אני נשאר איתך. רוצה שנמשיך לדבר עד שתחייג?"
    )


def _normalize_hebrew(text: str) -> str:
    """Normalize Hebrew text for matching: strip nikud, normalize whitespace."""
    # Remove Hebrew diacritics (nikud) U+0591-U+05C7
    text = re.sub(r"[\u0591-\u05C7]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _find_matches(text: str, patterns: list[str]) -> list[str]:
    return [p for p in patterns if re.search(p, text)]
