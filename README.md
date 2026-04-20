# PTSD-Ai 🎙️

> מערכת תמיכה קולית בעברית מבוססת RAG, מתמחה בפוסט-טראומה צבאית.
> חוויית שיחת טלפון — בלי כפתורים, בלי לחיצות. רק לדבר.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: PROPRIETARY](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

---

## ⚠️ הצהרה חשובה

**המערכת אינה תחליף לטיפול רפואי או נפשי מקצועי.**
המערכת אינה מאבחנת, אינה מספקת המלצות רפואיות, ואינה תחליף לפסיכולוג, פסיכיאטר, או קו חירום.
המערכת מהווה "אוזן קשבת" בלבד.

במצבי משבר → המערכת מפנה מיידית ל[ער"ן 1201](https://www.eran.org.il/) או [נט"ל 1-800-363-363](https://www.natal.org.il/).

---

## 🏗️ ארכיטקטורה

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Web Client  │────▶│              │     │                 │
│  (WebRTC)    │     │   LiveKit    │────▶│  Voice Agent    │
├──────────────┤     │   Server     │     │  (Python)       │
│  Phone Call  │────▶│  (Israel)    │     │                 │
│  (Twilio SIP)│     └──────────────┘     └────────┬────────┘
└──────────────┘                                   │
                                                   ▼
            ┌─────────────────────────────────────────────────┐
            │  Pipeline: VAD → STT → Safety → RAG → LLM → TTS │
            └─────────────────────────────────────────────────┘
                       │            │            │
                       ▼            ▼            ▼
                  ┌────────┐  ┌──────────┐  ┌──────────┐
                  │ ivrit- │  │  Qdrant  │  │ElevenLabs│
                  │   ai   │  │ (vectors)│  │   TTS    │
                  └────────┘  └──────────┘  └──────────┘
```

### מרכיבים

| שכבה | טכנולוגיה | מה היא עושה |
|------|-----------|--------------|
| **Voice Infra** | LiveKit Agents | תזמור שיחות, VAD, turn detection, התמודדות עם קטיעות |
| **STT (Speech-to-Text)** | ivrit-ai/whisper-large-v3-turbo | תמלול עברית streaming |
| **LLM** | Claude Sonnet 4.6 (default) / Gemma 4 31B (alt) | הבנה ויצירת תשובות |
| **TTS (Text-to-Speech)** | ElevenLabs Multilingual v2 | קול עברי טבעי |
| **Vector DB** | Qdrant | חיפוש סמנטי במאמרים |
| **Embeddings** | Cohere embed-multilingual-v3 | וקטורים לעברית |
| **Phone Gateway** | Twilio + LiveKit SIP | מספר טלפון 972 |
| **Hosting** | AWS il-central-1 (תל אביב) | low latency לישראל |

---

## 🚀 התחלה מהירה

### דרישות מקדימות

- Python 3.11+
- Docker + Docker Compose
- חשבונות + מפתחות API:
  - [LiveKit](https://livekit.io) (cloud או self-host)
  - [Anthropic](https://console.anthropic.com) (ל-Claude) או Google AI Studio (ל-Gemma)
  - [ElevenLabs](https://elevenlabs.io)
  - [Cohere](https://cohere.com) (embeddings)
  - [Twilio](https://twilio.com) (אופציונלי - לשיחות טלפון)

### התקנה

```bash
# 1. שכפל את הריפו
git clone https://github.com/<your-username>/ptsd-ai.git
cd ptsd-ai

# 2. צור virtualenv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. התקן תלויות
pip install -r requirements.txt

# 4. הגדר משתני סביבה
cp .env.example .env
# ערוך את .env והכנס את המפתחות שלך

# 5. הרם את Qdrant מקומית
docker-compose up -d qdrant

# 6. הזן מאמרים (אחרי ששמת קבצים ב-data/articles/)
python -m ingestion.ingest

# 7. הרץ את הסוכן
python -m agent.main

# 8. בטרמינל אחר - הרם את ה-frontend
cd frontend/web && python -m http.server 8000
# פתח http://localhost:8000
```

### הזנת מאמרים

שים את כל המאמרים שלך תחת `data/articles/`. נתמכים:
- `.pdf` - מאמרים אקדמיים
- `.md` / `.txt` - טקסט גולמי
- `.docx` - וורד
- `urls.txt` - קובץ עם URL בכל שורה לסקרייפינג

ראה [`ingestion/README.md`](ingestion/README.md) לפרטים מלאים.

---

## 📁 מבנה הפרוייקט

```
ptsd-ai/
├── agent/                  # סוכן השיחה (LiveKit)
│   ├── main.py            # entrypoint
│   ├── config.py          # הגדרות
│   ├── prompts.py         # פרומפטים בעברית
│   ├── safety.py          # זיהוי משברים, escalation
│   ├── rag.py             # RAG retrieval
│   └── voice.py           # STT/TTS/LLM providers
├── ingestion/             # עיבוד מאמרים → Qdrant
│   ├── ingest.py
│   ├── chunking.py        # chunking מותאם לעברית
│   └── loaders/           # טעינה לפי סוג קובץ
├── frontend/
│   ├── web/               # ממשק web (LiveKit JS SDK)
│   └── phone/             # קונפיגורציית Twilio SIP
├── infra/                 # Terraform + Docker עבור AWS il-central-1
├── data/articles/         # המאמרים שלך (לא ב-git)
├── docs/                  # תיעוד מפורט
│   ├── architecture.md
│   ├── safety.md          # ⚠️ קריטי - קרא לפני production
│   ├── deployment.md      # פריסה ל-AWS Tel Aviv
│   └── hebrew-tts.md      # בחירת קול והגייה
└── tests/
```

---

## 🔐 פרטיות ואבטחה

- **אין שמירת אודיו** - השיחות עוברות streaming בלבד.
- **מינון logs** - תמלילים נשמרים מוצפנים לצורך שיפור איכות בלבד, עם opt-out.
- **GDPR / חוק הגנת הפרטיות** - ראה `docs/privacy.md`.
- **No PII בלוגים** - שמות וזיהויים מוסתרים אוטומטית.

---

## 📊 latency targets

יעד total latency end-to-end (סוף דיבור משתמש → תחילת תגובה קולית): **< 1.5 שניות**.

| שלב | יעד |
|------|-----|
| VAD (זיהוי סוף דיבור) | 300-500 ms |
| STT (תמלול) | 200-400 ms (streaming) |
| Safety + RAG | 100-300 ms |
| LLM first token | 300-700 ms |
| TTS first audio chunk | 200-400 ms |
| Network (בתוך ישראל) | 30-80 ms |

ראה `docs/architecture.md#latency` להסברים והאופטימיזציות.

---

## 🤝 תרומה

זה פרוייקט קנייני. לשאלות פנו ל-[המייל שלך].

## 📜 רישיון

Proprietary. כל הזכויות שמורות.
