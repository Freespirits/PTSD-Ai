# 🎙️ Hebrew TTS - בחירת קול וכיול

## למה זה חשוב

הקול הוא הממשק. אם הקול נשמע רובוטי, מתנשא, או "מגוחך" - המשתמש לא יוכל
להיפתח. בעבור אפליקציה של תמיכה נפשית - איכות הקול = איכות החוויה.

מטרות:
- **טבעי** - לא רובוטי, לא flat
- **חם** - לא קליני
- **רגוע** - לא נמרץ או "מוכר"
- **ברור** - הגייה נכונה של עברית, כולל מילים לועזיות
- **לא מזדהה כפסיכולוג** - שלא ייצור ציפיות שווא

---

## ספקי TTS לעברית

### 1. ElevenLabs Multilingual v2 (ברירת מחדל)

**יתרונות:**
- הקול הכי טבעי בעברית הזמין כיום
- streaming מהיר (~200ms TTFB)
- אפשרות voice cloning (לבנות זהות ייחודית)
- שליטה על stability + similarity

**חסרונות:**
- יקר (~$0.30-0.50 לדקת אודיו)
- לפעמים שגיאות הגייה במילים נדירות
- ה-defaults רץ ב-data center אמריקאי (latency)

**איך לבחור voice:**
1. https://elevenlabs.io/voice-library
2. סנן: Language = Hebrew
3. הקשב ל-3-5 דוגמאות לכל קול - חשוב להאזין למילים עם נון סופית, ע, ח, ר (אלה ה"מבחנים" של איכות בעברית)
4. בחר 2-3 קולות לבדיקה עם משתמשים אמיתיים

**הגדרות מומלצות (ב-`agent/main.py`):**
```python
elevenlabs.TTS(
    api_key=...,
    voice=elevenlabs.Voice(
        id=settings.elevenlabs_voice_id,
        name="...",
        category="premade",
    ),
    model="eleven_multilingual_v2",
    language="he",
    # Voice settings (העבר ב-voice_settings אם ה-SDK תומך):
    # stability=0.45,         # נמוך יותר = יותר אקספרסיבי
    # similarity_boost=0.75,  # גבוה = יותר נאמן לקול המקור
    # style=0.30,             # רך / נינוח
    # use_speaker_boost=True,
)
```

### 2. Azure Neural TTS (חלופה זולה)

**קולות עבריים:**
- `he-IL-AvriNeural` - גברי, ניטרלי
- `he-IL-HilaNeural` - נשי, חמים יותר

**יתרונות:**
- זול בערך פי 10 מ-ElevenLabs
- אפשרות לארח באזור israelcentral (latency נמוך לישראל!)
- תמיכה ב-SSML מלא (שליטה ב-pause, pitch, rate)
- Custom Neural Voice (CNV) - אם רוצים voice cloning

**חסרונות:**
- הקול הסטנדרטי קצת יותר "רובוטי" מ-ElevenLabs
- ב-CNV האיכות עולה משמעותית, אבל דורש 30+ דקות training data

**SSML מומלץ לעברית רגישה:**
```xml
<speak version="1.0" xml:lang="he-IL">
  <voice name="he-IL-HilaNeural">
    <prosody rate="-10%" pitch="-2%">
      שלום. <break time="500ms"/>
      אני כאן בשבילך. <break time="300ms"/>
      קח את הזמן שלך.
    </prosody>
  </voice>
</speak>
```

### 3. Google Cloud TTS

**קולות:**
- `he-IL-Wavenet-A`, `he-IL-Wavenet-B`, `he-IL-Wavenet-C`, `he-IL-Wavenet-D`
- `he-IL-Standard-A`, `-B`, `-C`, `-D`

איכות סבירה, מחיר זהה ל-Azure. אם כבר על GCP - הגיוני.

### 4. Israeli startup options
- **Speechify** (כלל-עולמי, חלש בעברית)
- **AI21 Labs** - לא מציעים TTS
- אין כיום ספק ישראלי מקומי שתחרותי באיכות עבור TTS עברי

---

## טיפול בבעיות הגייה

### מילים לועזיות
ElevenLabs ו-Azure לפעמים מבטאים מילים לועזיות באנגלית-עם-מבטא-עברי במקום בעברית.
פתרונות:
1. הוסף `<phoneme>` SSML (Azure)
2. תרגם בפרומפט ל-LLM שיכתוב phonetic Hebrew במקום: `"PTSD"` → `"פי טי אס די"`
3. ב-pre-processing של ה-TTS, החלף בקבוע terms בכתיב מנוקד או פונטי.

### ראשי תיבות
- `צה"ל` → `צה הל` או `צבא ההגנה לישראל` (תלוי איך ElevenLabs מבטא את המקור)
- `צה"ל` עם גרשיים: בדוק שזה לא נשמע "צה כפול ציטוט ל"
- `בנט"ל` → `נטל` (4 אותיות יחד)

מומלץ pre-processing tier ב-`agent/voice.py` (להוסיף):
```python
HEBREW_PRONUNCIATION_FIXES = {
    "PTSD": "פי טי אס די",
    "צה\"ל": "צבא הגנה לישראל",
    "DSM-5": "די אס אם חמש",
    # ...
}

def fix_pronunciation(text: str) -> str:
    for k, v in HEBREW_PRONUNCIATION_FIXES.items():
        text = text.replace(k, v)
    return text
```

### מספרים
- `7` → "שבע" (לא "שבעה" - תלוי context!)
- `1201` → "אחד שתיים אפס אחד" (לא "אלף מאתיים ואחד")

הנחה את ה-LLM ב-system prompt לכתוב מספרים במילים, או הוסף שכבת normalization.

---

## כיול אישי

### שלב 1: בדיקת voice (3-5 קולות)
- הקלט 30 שניות מכל voice עם דוגמת תגובה אמיתית
- שלח ל-3-5 משתמשי בטא (עדיף עם רקע צבאי לקהל היעד)
- שאל: "איזה קול הכי גורם לך להרגיש בנוח לדבר?"

### שלב 2: כיול מהירות + רגוע
ב-PTSD support, מהירות דיבור מומלצת היא **80-90% מהמהירות הסטנדרטית**.
זה מרגיש יותר רגוע, נותן זמן לעיבוד.

ב-ElevenLabs - אין שליטה ישירה במהירות, אבל יש שליטה ב-`stability` (גבוה = יותר רגוע ומונוטוני).

ב-Azure - SSML `prosody rate="-10%"`.

### שלב 3: A/B testing בייצור
- חצי משיחות → voice A
- חצי משיחות → voice B
- מדוד: משך שיחה (ארוך יותר = משתמש מרגיש בנוח), survey rating, חזרה לשימוש

---

## עלויות (October 2025-ish prices)

| ספק | מחיר ל-1000 תווים | ל-1000 דקות שיחה (~750K תווים) |
|------|---------------------|----------------------------------|
| ElevenLabs Multilingual v2 | $0.30 (Creator tier) | $225 |
| ElevenLabs (Pro) | $0.18 | $135 |
| Azure Neural | $0.016 | $12 |
| Google Wavenet | $0.016 | $12 |

ElevenLabs יקר יותר ב-15-20x. אם קנה מידה גדל, שווה לעבור ל-Azure.

ההמלצה שלי: **התחל עם ElevenLabs בפיילוט** (איכות גבוהה, חוויה טובה),
ואז כשרוצים לסקייל - **עבור ל-Azure** (אם איכות מספקת) או **ElevenLabs Scale tier**.

---

## בדיקות איכות לפני production

קלף בדיקה - ודא שהקול הנבחר מבטא נכון:
- "שלום, איך אתה מרגיש היום?"
- "אני שומע אותך."
- "בוא נדבר על מה שקרה במילואים."
- "ער\"ן בקו אחד שתיים אפס אחד."
- "פוסט-טראומה, פלאשבק, התקף חרדה."
- "פגיעה, אובדן, חיילים, מפקד פלוגה."
- שמות מקומות: "צאלים, נחל עוז, רעים, חאן יונס."
- ביטויים: "מה שעובר עליך זה אמיתי. אתה לא לבד."

**הקלט את כל אלה. השמע ל-3 ישראלים. אם משהו צורם - שנה voice.**
