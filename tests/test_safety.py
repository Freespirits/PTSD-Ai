"""Tests for safety module.

Run: pytest tests/test_safety.py -v
"""

import pytest

from agent.safety import (
    assess_user_input,
    filter_agent_output,
    RiskLevel,
)


# =============================================================================
# Crisis detection - MUST trigger
# =============================================================================

CRISIS_INPUTS = [
    "אני רוצה להתאבד",
    "אני אתאבד הלילה",
    "אני לא רוצה להיות פה יותר",
    "אני לא רוצה לחיות",
    "החיים שלי לא שווים",
    "אני רוצה לפגוע בעצמי",
    "אני חותך את עצמי",
    "אני לא יכול לנשום עכשיו",
    "פלאשבק עכשיו, אני שם",
    "העולם יהיה יותר טוב בלעדיי",
]


@pytest.mark.parametrize("text", CRISIS_INPUTS)
def test_crisis_inputs_trigger(text):
    """Every CRISIS_INPUT must result in CRISIS risk and a hotline offer."""
    assessment = assess_user_input(text)
    assert assessment.risk == RiskLevel.CRISIS, f"Failed to detect crisis: {text!r}"
    assert assessment.require_hotline_offer is True
    assert assessment.suggested_response is not None
    # Must mention at least one hotline number
    assert ("1201" in assessment.suggested_response
            or "363" in assessment.suggested_response)


# =============================================================================
# Elevated distress - should at least flag
# =============================================================================

ELEVATED_INPUTS_SINGLE = [
    "אני שבור",
    "אני קרוס",
    "אני לא יכול יותר",
    "אין לי כוח",
    "אני מרגיש ריק",
    "אף אחד לא מבין",
    "יש לי סיוטים כל לילה",
]


@pytest.mark.parametrize("text", ELEVATED_INPUTS_SINGLE)
def test_elevated_single(text):
    assessment = assess_user_input(text)
    assert assessment.risk in (RiskLevel.ELEVATED, RiskLevel.HIGH)


def test_elevated_multiple_becomes_high():
    text = "אני שבור, אני קרוס, אין לי כוח יותר, אני מרגיש ריק"
    assessment = assess_user_input(text)
    assert assessment.risk == RiskLevel.HIGH
    assert assessment.require_hotline_offer is True


# =============================================================================
# Normal inputs - should NOT trigger false positives
# =============================================================================

NORMAL_INPUTS = [
    "שלום, איך אתה?",
    "אני רוצה לדבר על מה שקרה במילואים",
    "היה לי שבוע קשה בעבודה",
    "אני זוכר שהייתי בלבנון בתשעים ושמונה",
    "בא לי לישון אבל אני לא יכול",  # tricky - "לא יכול" alone shouldn't fire
    "המילואים האחרונים היו ממש קשים",
    "אני מעולם לא דיברתי על זה",
]


@pytest.mark.parametrize("text", NORMAL_INPUTS)
def test_normal_inputs_no_crisis(text):
    """These shouldn't escalate to CRISIS - false positives erode trust."""
    assessment = assess_user_input(text)
    assert assessment.risk != RiskLevel.CRISIS, f"False positive: {text!r}"


# =============================================================================
# Output filtering - catch medical advice
# =============================================================================

MEDICAL_ADVICE_OUTPUTS = [
    "אני ממליץ שתיקח SSRI",
    "קח כדור הרגעה לפני השינה",
    "האבחנה שלך היא PTSD",
    "יש לך דיכאון, צריך טיפול",
    "מינון של חצי כדור יעזור",
]


@pytest.mark.parametrize("text", MEDICAL_ADVICE_OUTPUTS)
def test_medical_advice_flagged(text):
    _, warnings = filter_agent_output(text)
    assert len(warnings) > 0, f"Failed to flag medical advice: {text!r}"


SAFE_OUTPUTS = [
    "אני שומע אותך. זה נשמע ממש קשה.",
    "ספר לי עוד על מה שאתה מרגיש.",
    "מה עוזר לך לרוב כשזה קורה?",
    "זה מובן לחלוטין שאתה מרגיש ככה.",
]


@pytest.mark.parametrize("text", SAFE_OUTPUTS)
def test_safe_outputs_not_flagged(text):
    _, warnings = filter_agent_output(text)
    assert len(warnings) == 0, f"False positive on safe output: {text!r}"


# =============================================================================
# Edge cases
# =============================================================================

def test_empty_input():
    assessment = assess_user_input("")
    assert assessment.risk == RiskLevel.NONE


def test_nikud_normalization():
    """Hebrew with diacritics (nikud) should still match patterns."""
    text_with_nikud = "אֲנִי רוֹצֶה לְהִתְאַבֵּד"
    assessment = assess_user_input(text_with_nikud)
    assert assessment.risk == RiskLevel.CRISIS
