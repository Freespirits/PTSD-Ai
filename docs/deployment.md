# 🚀 Deployment - פריסה לשרת ישראלי (Low Latency)

מטרה: לארח את כל המערכת באזור גיאוגרפי בישראל כדי שלמשתמשים תהיה latency מינימלית.

---

## אופציות hosting בישראל

| ספק | אזור | יתרונות | חסרונות |
|------|-------|----------|----------|
| **AWS** | il-central-1 (Tel Aviv) | 3 AZs, full service catalog, נפתח 2023 | יקר יחסית |
| **Azure** | israelcentral | יש Hebrew TTS native, integration עם Microsoft 365 | מעט פחות שירותים מ-AWS |
| **Google Cloud** | me-west1 (Tel Aviv) | זול יחסית, יש Vertex AI לארח Gemma 4 | פחות resources לאזור |
| **Oracle Cloud** | il-jerusalem-1 | זול | Ecosystem מצומצם |
| **ספקים מקומיים** | Bynet, Triple-C | תמיכה בעברית, סוברניות | פחות אוטומציה, יקר ב-scale |

**ההמלצה שלי:**
- אם משתמשים ב-Gemma 4 self-hosted → **GCP me-west1** (Vertex AI עם Gemma מובנה)
- אחרת → **AWS il-central-1** (תיעוד הכי טוב, ecosystem עשיר)

המדריך הבא ל-AWS, אבל הקונספט זהה לכולם.

---

## ארכיטקטורה ב-AWS

```
                Internet
                   │
         ┌─────────┴─────────┐
         │   CloudFront +    │  ← TLS termination, WAF, DDoS protection
         │       WAF         │
         └─────────┬─────────┘
                   │
         ┌─────────┴─────────┐
         │   ALB (il-central-1)│
         └─────────┬─────────┘
                   │
       ┌───────────┼───────────┐
       ↓           ↓           ↓
  ┌─────────┐ ┌─────────┐ ┌─────────┐
  │ web     │ │ token-  │ │ agent   │  ← ECS Fargate / EKS
  │ (nginx) │ │ server  │ │ worker  │
  └─────────┘ └─────────┘ └────┬────┘
                                │
                       ┌────────┴────────┐
                       │ LiveKit Cloud   │  ← managed (או self-host)
                       └────────┬────────┘
                                │
                       ┌────────┴────────┐
                       │ ivrit-ai STT    │  ← EC2 g4dn.xlarge (GPU)
                       │ (אם self-host)  │
                       └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │     Qdrant      │  ← EC2 r6i.large + EBS
                       │  (vector DB)    │
                       └─────────────────┘
```

---

## שלבי פריסה (high-level)

### 1. הקמת VPC + רשת
```bash
# VPC עם 3 AZs ב-il-central-1
# Public subnets לפניים, private subnets ל-backend
# NAT gateway אחד (או אחד per AZ אם high availability)
```
Terraform template ב-`infra/terraform/network.tf` (להוסיף).

### 2. Container registry + builds
```bash
# צור ECR repo
aws ecr create-repository --repository-name ptsd-ai/agent --region il-central-1

# build & push
docker build -t ptsd-ai/agent .
docker tag ptsd-ai/agent:latest <account>.dkr.ecr.il-central-1.amazonaws.com/ptsd-ai/agent:latest
aws ecr get-login-password --region il-central-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.il-central-1.amazonaws.com
docker push <account>.dkr.ecr.il-central-1.amazonaws.com/ptsd-ai/agent:latest
```

### 3. סודות ב-Secrets Manager
```bash
aws secretsmanager create-secret --name ptsd-ai/anthropic-key --secret-string "sk-ant-..."
aws secretsmanager create-secret --name ptsd-ai/elevenlabs-key --secret-string "..."
aws secretsmanager create-secret --name ptsd-ai/cohere-key --secret-string "..."
# ...וכו'
```

### 4. Qdrant על EC2
```bash
# r6i.large (2vCPU, 16GB RAM) מספיק להתחלה
# EBS gp3 100GB
# רץ Qdrant Docker בתוך EC2

ssh ec2-user@qdrant-host
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  --restart unless-stopped \
  qdrant/qdrant:latest
```

לעדיפות גבוהה יותר: Qdrant Cloud (managed) באזור AWS Tel Aviv אם זמין.

### 5. ivrit-ai STT (אם self-hosting)
```bash
# g4dn.xlarge (4vCPU, 16GB RAM, T4 GPU)
# או g5.xlarge (יותר מהיר, A10G)
# AMI: Deep Learning Base AMI

# Run faster-whisper-server:
docker run -d --gpus all -p 8001:8000 \
  -v whisper_models:/root/.cache/huggingface \
  -e WHISPER__MODEL=ivrit-ai/whisper-large-v3-turbo \
  fedirz/faster-whisper-server:latest-cuda
```

### 6. ECS Fargate ל-agent + token-server
ראה `infra/terraform/ecs.tf` (להוסיף).

תקציר:
- Fargate task definition לכל service
- Service Discovery (Cloud Map) לתקשורת פנימית
- Auto-scaling: 2 → 20 tasks לפי CPU/Memory

### 7. ALB + Route 53 + ACM
- ALB עם target groups ל-web ול-token-server
- ACM certificate עבור הדומיין
- Route 53 לDNS

### 8. CloudFront + WAF
- CloudFront מול ALB
- WAF rules:
  - Rate limiting: 100 req / 5 min per IP
  - Block SQL injection / XSS attempts (managed rules)
  - Geographic restriction אם רלוונטי

---

## ביצועים: בדיקות latency

אחרי פריסה, מדוד מתוך ישראל:

```bash
# DNS resolution + connection
curl -w "@curl-format.txt" -o /dev/null -s https://yourdomain.example/health
```

יעדים:
- DNS: < 30ms
- TCP connect: < 50ms
- TLS handshake: < 100ms
- Total to /health: < 200ms

אם גבוה משמעותית - ייתכן שיש routing דרך ארה"ב/אירופה. בדוק:
```bash
mtr -r yourdomain.example
```

---

## עלות צפויה (חודשי, לתפוקה של 1000 שיחות / יום, ממוצע 5 דק')

| שירות | תצורה | עלות (USD) |
|--------|---------|------------|
| ECS Fargate (agent + token, 2 tasks each) | 0.5 vCPU, 1GB | $40 |
| EC2 g5.xlarge (ivrit-ai STT) | 1 instance, on-demand | $730 |
| EC2 r6i.large (Qdrant) | 1 instance + 100GB EBS | $90 |
| ALB | | $20 |
| CloudFront | 100GB egress | $10 |
| Data transfer (egress to internet) | | $40 |
| Secrets Manager | 10 secrets | $4 |
| **AWS subtotal** | | **~$934** |
| Anthropic Claude (input + output) | ~150K tokens/call * 1000 * 30 | $400 |
| ElevenLabs (Creator → Pro tier) | 1M chars/month + | $99-330 |
| Cohere embeddings | minimal (one-time + queries) | $20 |
| LiveKit Cloud (alternative to self-host) | 50K minutes | $300 |
| **Total monthly (rough)** | | **$1,750-2,000** |

### חיסכון
- Reserved Instances ל-EC2 (-30%)
- Spot Instances ל-non-critical (-70%)
- Self-host LiveKit (-$300)
- Self-host Gemma 4 במקום Claude (-$400, אבל +$300 GPU costs)
- Azure TTS במקום ElevenLabs (-$200, אבל איכות יורדת קצת)

---

## High availability

### Multi-AZ
- ALB ב-3 AZs
- ECS tasks ב-3 AZs
- Qdrant: snapshot ל-S3 כל שעה (single-AZ ב-tier הזה, multi-node ב-scale)
- LiveKit: managed (LiveKit Cloud), או cluster של 3+ nodes ב-self-hosted

### Disaster recovery
- RPO (Recovery Point Objective): 1 שעה (Qdrant snapshots)
- RTO (Recovery Time Objective): 30 דקות
- Backup region: eu-south-1 (Milan) או eu-west-1 (Ireland) - כל-לא-ישראלי בגלל ש-il-central-1 הוא פעיל בלבד אזור אחד

---

## Compliance checklist

- [ ] **חוק הגנת הפרטיות (ישראל)** - data residency, breach notification
- [ ] **GDPR** (אם יש משתמשים מאירופה)
- [ ] **רישום במאגרי מידע** (חוק ישראלי - דורש רישום למאגרים שמכילים מידע רגיש)
- [ ] **Privacy Policy** + **Terms of Service** מפורסמים
- [ ] **DPA** עם כל ספק:
  - LiveKit
  - Anthropic / OpenAI / Google
  - ElevenLabs
  - Cohere
  - AWS

---

## CI/CD

מומלץ GitHub Actions:
1. Pull request → run tests + ruff + mypy
2. Merge to main → build Docker image, push to ECR
3. Manual approval → deploy to staging
4. Manual approval → deploy to production (blue/green)

טיוטת workflow ב-`.github/workflows/deploy.yml` (להוסיף).

---

## Incident response

אם משהו נשבר ב-3 לפנות בוקר:

1. **Page on-call** (PagerDuty / Opsgenie)
2. **Status page** מתעדכן אוטומטית
3. **Crisis hotline fallback** - אם המערכת down, ה-website צריך להציג בולט:
   > "המערכת אינה זמינה כעת. במצוקה - ער"ן 1201, נט"ל 1-800-363-363, מד"א 101"
4. **Postmortem** תוך 48 שעות (blameless)
