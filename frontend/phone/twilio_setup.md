# 📞 חיבור מספר טלפון ישראלי (Twilio + LiveKit SIP)

מטרה: משתמש מחייג למספר 972 רגיל ומקבל את אותו הסוכן הקולי שיש בממשק ה-Web.

## ארכיטקטורה

```
[משתמש מחייג] → [Twilio +972] → [LiveKit SIP Trunk] → [Voice Agent (אותו אחד!)]
```

ה-Voice Agent לא צריך לדעת שזו שיחת טלפון - LiveKit מטפל בגישור.

---

## שלב 1: רכישת מספר ישראלי ב-Twilio

ל-Twilio יש זמינות מוגבלת למספרים ישראליים. אופציות:

| סוג | זמינות | מחיר חודשי | הערות |
|------|---------|-------------|--------|
| Mobile (+972 5x) | מוגבל מאוד, דורש הגשת מסמכים | ~$15 | התהליך לוקח שבועות. דורש כתובת + ת.ז. |
| Local (+972 3, +972 2 וכו') | זמין יותר | ~$5-10 | קל יותר להשיג |
| Toll-free (+972 1-800) | זמין דרך partners | יותר יקר | אופציה הכי טובה למוקדי תמיכה |

**חלופות אם Twilio קשה מדי:**
- **Vonage** (חברה ישראלית במקור) - ידידותית יותר למספרים ישראליים
- **Bynet Voice / 013 Netvision** - ספקי VoIP ישראליים, נדרש לבד SIP trunk
- **Voca** - חברה ישראלית

המדריך כאן מתמקד ב-Twilio (הכי תיעוד), אבל הקונספט זהה לכולם.

### רכישה ב-Twilio Console
1. https://console.twilio.com/us1/develop/phone-numbers/manage/search
2. Country: Israel
3. Capabilities: **Voice** (SMS לא נדרש)
4. Buy

### הגשת מסמכים (Address + ID)
ישראל היא "regulated country" - דרושה הגשת:
- מסמך זיהוי של מי שרוכש (ת.ז.)
- אישור כתובת (חשבון חשמל / מים, עד 3 חודשים)
- במקרה של חברה - אישור רישום חברה

הגשה דרך https://console.twilio.com/us1/develop/phone-numbers/regulatory-compliance

---

## שלב 2: יצירת SIP Trunk ב-LiveKit

### LiveKit Cloud (הכי פשוט)
```bash
# התקן livekit-cli
brew install livekit-cli   # mac
# או: curl -sSL https://get.livekit.io/cli | bash

# Login
lk cloud auth

# צור Inbound SIP Trunk
lk sip inbound create \
  --name "twilio-inbound" \
  --numbers "+9723XXXXXXX"
```

תקבל בתשובה:
- `trunk_id` - שמור ב-`.env` בתור `LIVEKIT_SIP_TRUNK_ID`
- `sip_uri` - לדוגמה `sip:abc123.sip.livekit.cloud`

### LiveKit self-hosted
ראה https://docs.livekit.io/sip/quickstart/ - דורש הרצת `sip-server` נוסף.

---

## שלב 3: הפניית Twilio ל-LiveKit

ב-Twilio Console → Phone Numbers → Manage → Active Numbers → המספר שרכשת:

**Voice Configuration:**
- A call comes in: `SIP`
- SIP URI: `sip:<your-livekit-sip-uri>?x-region=il`

או אם אתה מעדיף TwiML/webhook:
- A call comes in: `Webhook`
- URL: `https://yourdomain.example/twilio/voice` (יחזיר TwiML עם `<Dial><Sip>...</Sip></Dial>`)

---

## שלב 4: Dispatch Rule ב-LiveKit

הגדרה שאומרת ל-LiveKit "כל שיחת SIP נכנסת - שלח לחדר חדש והפעל את הסוכן":

```bash
lk sip dispatch create \
  --trunk-id <your_trunk_id> \
  --rule '{"dispatchRuleIndividual": {"roomPrefix": "phone-call-"}}' \
  --agent-name "ptsd-ai-agent"
```

בקובץ `agent/main.py`, ודא שאתה מעלה את הסוכן עם שם זהה:

```python
cli.run_app(
    WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="ptsd-ai-agent",  # <-- זה
        ...
    )
)
```

---

## שלב 5: בדיקה

1. הרץ את הסוכן: `python -m agent.main start`
2. חייג למספר שרכשת
3. אמור להישמע הברכה (`GREETINGS_HE` מ-`agent/prompts.py`)

### אם אתה לא שומע כלום
- בדוק ב-LiveKit Dashboard → SIP → Recent Calls
- בדוק ב-Twilio → Monitor → Logs → Calls
- ודא ש-`elevenlabs_voice_id` ב-`.env` הוא של קול תומך עברית

---

## עלויות צפויות

לשיחה של 5 דקות (הערכה):
- Twilio inbound: ~$0.05
- LiveKit SIP minutes: ~$0.02
- ElevenLabs TTS (~750 תווים/דקה * 5 = 3750): ~$0.06
- Claude Sonnet input+output (כולל RAG): ~$0.04
- ivrit-ai STT (self-hosted): ~$0.01 compute

**סה"כ: ~$0.18 לשיחה של 5 דקות.** בקנה מידה גדול תרצה לעבור ל-Hebrew TTS זול יותר (Azure neural voices: ~$0.016 ל-1000 תווים) או לארח בעצמך.

---

## אבטחה

- **אל תחשוף** את ה-`sip_uri` בקוד client. רק Twilio צריך לדעת.
- בעת שימוש ב-Webhook, חתום בקשות ב-Twilio signature וודא ב-FastAPI.
- הגבל מספרי מקור אם רלוונטי (חוסם spam calls).
- שקול הוספת captcha קולי ראשוני אם השירות נפתח לקהל הרחב.
