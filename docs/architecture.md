# 🏗️ Architecture - מסמך טכני

## סקירה

PTSD-Ai הוא Voice AI agent שעובד כמו שיחת טלפון: המשתמש מתקשר (web או טלפון),
המערכת מקשיבה, מתייעצת ב-RAG, ומחזירה תגובה קולית בעברית - כל זה בתוך
פחות משנייה וחצי.

## רכיבים

### 1. Voice Infrastructure: LiveKit
**למה LiveKit?**
- בנוי במיוחד ל-real-time voice agents
- מטפל ב-VAD, turn detection, interruption handling out of the box
- תמיכה native בגישור SIP (לטלפון) + WebRTC (לדפדפן)
- streaming בשני הכיוונים
- Open source, אפשר לארח בעצמך

**אלטרנטיבות שנשקלו:**
- Pipecat (Daily) - דומה, גם טוב, פחות בוגר
- WebRTC ישיר + Twilio - יותר עבודה, פחות features
- בנייה מאפס - לא הגיוני בלוח הזמנים

### 2. STT: ivrit-ai / Whisper
**למה ivrit-ai?**
- Whisper-large-v3-turbo שעבר fine-tuning על עברית
- WER (word error rate) טוב משמעותית מ-Whisper הסטנדרטי בעברית
- רץ self-hosted (פרטיות + עלות)
- streaming תמיכה דרך faster-whisper

**אלטרנטיבות:**
- Azure Speech (he-IL) - נוח, יקר יותר, latency גבוה יותר
- OpenAI Whisper API - לא streaming, לא אופטימלי
- Google Speech-to-Text - תמיכת עברית סבירה

### 3. LLM: Claude Sonnet (default)
ראה `docs/llm-comparison.md` להשוואה מפורטת.

תקציר:
- **Claude Sonnet 4.6+**: ברירת מחדל. עברית מצוינת, מהיר.
- **GPT-4o**: חלופה equivalent.
- **Gemma 4 31B (self-hosted)**: open-source, sovereign hosting, עלות נמוכה אחרי setup ראשוני, אבל עברית פחות "טבעית" ב-edge cases של אמפתיה.
- **DictaLM 2.0**: עברית native, אבל קטן (7B) ופחות טוב באמפתיה.

המערכת model-agnostic - מחליפים ב-`.env` בלבד.

### 4. TTS: ElevenLabs Multilingual v2
**למה ElevenLabs?**
- הקול הכי טבעי בעברית
- streaming - האודיו מתחיל לזרום תוך ~200ms
- voice cloning אם תרצה לבנות זהות קולית ייחודית

**אלטרנטיבות:**
- Azure Neural TTS (Avri / Hila) - הרבה יותר זול, איכות סבירה
- Google Cloud TTS (Wavenet he-IL-A/B) - דומה ל-Azure

### 5. Vector DB: Qdrant
- Self-hostable, fast (Rust)
- תמיכה ב-payload filtering, hybrid search
- API פשוט

**אלטרנטיבות:** pgvector (אם כבר יש Postgres), Pinecone (managed).

### 6. Embeddings: Cohere multilingual-v3
- 1024 dim, תומך עברית מצוין
- מבדיל בין search_query ל-search_document (דיוק טוב יותר)

**אלטרנטיבות:** OpenAI text-embedding-3-large, AlephBERT (Hebrew-specific).

---

## Latency Budget

יעד total: **< 1.5s** מסוף דיבור משתמש → תחילת תגובה קולית.

```
משתמש מסיים לדבר
  ↓ 300-500ms     VAD detect end of speech (Silero VAD)
  ↓ 200-400ms     STT finishes transcribing (streaming, אז מתחיל מוקדם יותר)
  ↓ 30-100ms      Safety check (regex, מהיר)
  ↓ 80-200ms      RAG: embedding + Qdrant query (במקביל, אם Qdrant באותו DC)
  ↓ 300-700ms     LLM first token (Claude streaming)
  ↓ 200-400ms     TTS first audio chunk (ElevenLabs streaming)
  ↓ 30-80ms       Network (בתוך il-central-1)
  =
  ~1.1-2.4s
```

### אופטימיזציות
1. **Streaming everywhere**. STT, LLM, TTS - הכל streaming. אין batching.
2. **Parallel safety + RAG** - שתי הפעולות לא תלויות.
3. **VAD tuning**: `min_silence_duration=0.4s` - איזון בין latency לבין הימנעות מקטיעות מוקדמות.
4. **Connection pooling** ל-Qdrant ולספקי API.
5. **Prompt caching** ב-Anthropic API (the system prompt + RAG context הם גדולים).
6. **Edge proximity**: שרת באזור il-central-1 (Tel Aviv) מקטין latency לישראלים בכ-100-150ms.

### Latency שצריך לחיות איתה
- ElevenLabs API נמצאת בארה"ב/אירופה. round-trip ~80-150ms. אם זה קריטי, שקול Azure TTS באזור israelcentral.
- Anthropic API - אזור גיאוגרפי לא ניתן לבחירה. round-trip ~100-200ms.

---

## Concurrency model

### Per call
- LiveKit יוצר חדר אחד לכל call
- Voice agent מחובר לחדר אחד בכל פעם
- Worker יחיד יכול לטפל ב-N agents במקביל (configurable)

### Scaling
- Horizontal: הפעל יותר workers. LiveKit מאזן לבד.
- Vertical: יותר זיכרון/CPU per worker (אם self-hosting STT/LLM).

### Bottlenecks צפויים
1. **Self-hosted STT GPU** - אם משתמשים ב-ivrit-ai self-hosted: דרוש GPU עם זיכרון מספיק (~10GB ל-large-v3-turbo).
2. **API rate limits**:
   - Anthropic: tier 2+ מספיק לכמה עשרות שיחות במקביל
   - ElevenLabs: tier "Creator" - 5 concurrent generations. Production tier - 10+. צור מנוי "Scale" אם הולך production.
3. **Qdrant** - יכול לטפל באלפי queries/sec, לא bottleneck בקנה מידה צפוי.

---

## Failure modes

### STT נכשל
- LiveKit יחזור על השליחה (built-in retry)
- אם נכשל שוב: הסוכן יגיד "סליחה, לא שמעתי. תוכל לחזור?"
- Log + alert

### LLM timeout / שגיאה
- `tenacity` retry עם backoff
- fallback: תגובה גנרית "תן לי שנייה לחשוב..." (משחק על הזמן)
- Sentry alert

### TTS נכשל
- אופציונלית: fallback ל-Azure TTS או Google
- אם הכל נכשל: notification למשתמש (הודעת טקסט ב-UI), כי השיחה הקולית נשברה

### Crisis detection מסמן false positive
- לא נורא. עדיף הצעה מיותרת מהחמצה.
- אבל לא רוצים לשגע משתמשים, אז:
  - על trigger בודד (`ELEVATED`) - תזכיר בעדינות
  - על trigger מרובה (`HIGH/CRISIS`) - הסלם בנחישות

### משתמש מתנתק באמצע
- LiveKit מזהה (Disconnected event)
- Agent עוצר, משחרר משאבים
- Log

---

## Observability

### מטריקות לעקוב
- Calls per minute / hour / day
- Average call duration
- p50/p95/p99 end-to-end latency
- Crisis triggers per call
- STT WER (אם יש ground truth)
- TTS / LLM API errors per minute
- Cost per call

### כלים
- **Sentry** - exceptions, slow queries
- **Prometheus + Grafana** - מטריקות אופרטיביות
- **LiveKit dashboard** - call analytics out of the box
- **OpenTelemetry** - distributed tracing אם הפרוייקט גודל

---

## Security

ראה `docs/safety.md` לפרטיות + `docs/deployment.md` לאבטחת תשתית.

תקציר:
- TLS בכל מקום
- Tokens קצרי-חיים (30 דקות) מהשרת token-server
- Secrets ב-AWS Secrets Manager (לא ב-env files ב-production)
- WAF מול nginx
- Rate limiting per IP
- DDoS protection (Cloudflare / AWS Shield)
