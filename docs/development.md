# פיתוח מקומי - מדריך מהיר

## הקמה ראשונית (פעם אחת)

```bash
# 1. Clone
git clone git@github.com:<your-username>/PTSD-Ai.git
cd PTSD-Ai

# 2. Virtual env
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip

# 3. תלויות
pip install -r requirements.txt

# 4. הגדרות
cp .env.example .env
# ערוך את .env ותוסיף את המפתחות שלך

# 5. Qdrant
docker-compose up -d qdrant
```

## זרימה יומיומית

```bash
# הפעל Qdrant אם הוא לא רץ
docker-compose up -d qdrant

# הזן מאמרים (אם יש חדשים)
python -m ingestion.ingest

# הרץ את הסוכן
python -m agent.main dev

# בטרמינל שני - הרץ את ה-token server
uvicorn agent.token_server:app --reload --port 8080

# בטרמינל שלישי - הגש את ה-web UI
cd frontend/web && python -m http.server 8000

# פתח http://localhost:8000?url=<LIVEKIT_URL>&token=<DEV_TOKEN>
# (או דרך /api/livekit-token שזה מה שהדפדפן ינסה ראשון)
```

## בדיקות

```bash
# כל הטסטים
pytest

# טסטים ספציפיים
pytest tests/test_safety.py -v
pytest tests/test_chunking.py -v

# Coverage
pytest --cov=agent --cov=ingestion --cov-report=term-missing
```

## בדיקת סגנון קוד

```bash
ruff check .              # lint
ruff format .             # format
mypy agent ingestion      # type check
```

## דיבאגים נפוצים

### "Failed to connect to Qdrant"
```bash
docker-compose ps   # ודא ש-qdrant רץ
docker-compose logs qdrant
```

### "No Hebrew voice found"
עבור לתוך ElevenLabs dashboard, מצא `voice_id` של voice עברי שאתה אוהב,
ותכניס ל-`.env` בתור `ELEVENLABS_VOICE_ID`.

### "STT returns gibberish"
- ודא ש-`STT_PROVIDER=ivrit_ai` ושהשרת רץ ב-`http://localhost:8001`
- נסה עם audio פשוט (`python -m agent.smoke_stt sample.wav`)
- לחלופין, נסה zamar `STT_PROVIDER=openai_whisper` כ-smoke test

### "LLM says English even though prompt is Hebrew"
ודא שה-`LLM_MODEL` הוא גרסה שתומכת בעברית היטב. Claude Sonnet תמיד יענה בעברית
אם ה-system prompt וה-user message בעברית. עבור Gemma 4, הוסף בפירוש בסוף
ה-system prompt: "ענה תמיד בעברית."

## git hooks (אופציונלי)

```bash
# pre-commit hook שמריץ ruff לפני commit
cat > .git/hooks/pre-commit <<'EOF'
#!/usr/bin/env bash
ruff check --fix agent ingestion tests
ruff format agent ingestion tests
EOF
chmod +x .git/hooks/pre-commit
```
