# IPL FanZone — Deployment & Production Guide

**Updated**: September 8, 2026
**Tests**: 43/43 passing ✅
**Stack**: Django 4.2 + Channels (daphne) + SQLite + Groq AI + Cricbuzz scraping

---

## 1. What's in the box

| Capability | Where | Free-tier impact |
|---|---|---|
| Jarvis AI — **offline-first** RAG | `apps/ai_bot/rag.py` | Most stat answers cost **0 Groq quota** |
| LangChain orchestration (optional) | `requirements-rag.txt` + `USE_LANGCHAIN_RAG=true` | Not installed by default (keeps images small) |
| Fine-tune dataset | `manage.py build_finetune_dataset` → `data/finetune_ipl.jsonl` | Generated locally, committed file optional |
| **Per-user + global rate limits** | `ipl_platform/ratelimit.py` + `settings.RATE_LIMITS` | Protects the shared Groq free key (see §4) |
| GDPR/CCPA privacy app | `apps/privacy/` → `/privacy/`, `/privacy/my-data/` | Consent banner gates embeds + memory writes |
| Live-score WebSocket `/ws/live/` | `apps/chat/consumers.py` + `static/js/live.js` | Auto-falls back to polling on serverless |
| IPL-first live classifier | `apps/scorecard/views.classify_match()` | Shows any live cricket; flags IPL LIVE |
| Scraper ban protection | `apps/scorecard/views.py` (90s gap + 30-min cache) | ~48 Cricbuzz fetches/day max |

---

## 2. Environment variables (single source of truth: `.env.example`)

```env
SECRET_KEY=          # generate: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DEBUG=False
ALLOWED_HOSTS=your-domain.com            # comma-separated
CSRF_TRUSTED_ORIGINS=https://your-domain.com
SITE_URL=https://your-domain.com

GROQ_API_KEY=        # https://console.groq.com/keys
GROQ_MODEL=openai/gpt-oss-20b            # pick a LIVE model: console.groq.com/docs/models
USE_LANGCHAIN_RAG=false                  # true only after pip install -r requirements-rag.txt

# Rate limits (count/period: s,m,h,d) — tune per-plan:
JARVIS_RATE_PER_MINUTE=10/m
JARVIS_RATE_PER_DAY=50/d
JARVIS_GLOBAL_PER_DAY=1000/d             # safety fuse for the shared free key
LIVE_API_RATE_PER_MINUTE=30/m
PRIVACY_API_RATE_PER_MINUTE=10/m

# Optional
# DB_ENGINE/DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT   (settings_production.py)
# CACHE_BACKEND=django.core.cache.backends.redis.RedisCache   # multi-worker deployments
# CACHE_LOCATION=redis://...
```

`.env` is git- AND docker-ignored. Secrets enter via the platform's tooling (§5).

---

## 3. Free deployment targets

| Platform | Always free | WebSockets | Deliver | Caveats |
|---|---|---|---|---|
| **Hugging Face Spaces** | ✅ | ✅ | Docker space | Public space by default |
| **Render** | ✅ 750 h/mo | ✅ | `dockerfile` → Web Service | Sleeps 15 min idle (~30 s cold start) |
| **Fly.io** | ✅ allowance | ✅ | `fly launch` (auto-detects Dockerfile) | 256 MB shared CPU |
| **Google Cloud Run** | 2M req/mo free | ✅ | `gcloud run deploy` (§5.2) | Scales to zero = cold starts |
| **Oracle Always Free VM** | ✅ biggest | ✅ | Docker on the VM | You manage the OS |
| **Vercel** | ✅ generous | ❌ | `vercel.json` (WSGI) | No WS → polling fallback; read-only FS |

**Smallest-effort path**: `docker build -f dockerfile -t ipl-fanzone . && docker run -p 8080:8080 --env-file .env ipl-fanzone` — identical locally and on every Docker-capable host.

### One-time data prep (do locally, commit results)
```bash
python manage.py migrate
python manage.py process_ipl_data        # → data/ipl_processed.json (26 KB, tracked on purpose)
python manage.py build_finetune_dataset  # optional → data/finetune_ipl.jsonl (git-ignored)
```

---

## 4. Rate-limit design (avoid bans + quota burn)

**Groq (Jarvis) — enforced right before the API call** (`ask_ai`):
- `jarvis_user_minute` / `jarvis_user_day`: keyed by **anonymous session id** (SHA-256 hashed; falls back to client IP when sessions can't persist, e.g. serverless SQLite).
- `jarvis_global_day`: one counter for the whole site — the fuse that keeps a viral day from finishing a 14.4k-req/day free key.
- Offline answers (`source=offline`) and canned replies **never increment** any AI counter. 429 → JSON `{response, rate_limited, retry_after}` + `Retry-After` header; the chat UI shows a live countdown on the send button.

**Live-score JSON APIs**: `live_api_minute` per user.
**Privacy endpoints**: 10/min per user.
**Cricbuzz scraping**: separate upstream limiter — 1 fetch/90 s, 30-min cache, mock fallback. Two layers (fetch gap + cache) mean no IP bans.

Backend: Django cache — `locmem` by default (single process free tiers), Redis shared counters by setting `CACHE_BACKEND`/`CACHE_LOCATION`. Fails **open** if the cache backend dies (users are never locked out by an infra hiccup).

---

## 5. Secrets on each platform (no code changes needed — everything is `os.getenv`)

### 5.1 Vercel
Dashboard → Project → **Settings → Environment Variables** (scope Production/Preview), or:
```bash
vercel env add GROQ_API_KEY production
vercel env add SECRET_KEY production
vercel env add CSRF_TRUSTED_ORIGINS production   # https://<app>.vercel.app
vercel --prod        # env changes require a redeploy
```
Serverless notes: WS/chat rate-limiting falls back to IP-based counters; Jarvis memory file won't persist; DB is ephemeral per-invocation.

### 5.2 Google Cloud Run (+ Secret Manager — best fit, full WS support)
```bash
echo -n "sk_..."    | gcloud secrets create groq-api-key --data-file=-
echo -n "django.."  | gcloud secrets create django-secret-key --data-file=-

gcloud run deploy ipl-fanzone \
  --image gcr.io/PROJECT_ID/ipl-fanzone --allow-unauthenticated \
  --set-env-vars "DEBUG=False,ALLOWED_HOSTS=RUN_URL,CSRF_TRUSTED_ORIGINS=https://RUN_URL,SITE_URL=https://RUN_URL" \
  --set-secrets "GROQ_API_KEY=groq-api-key:latest,SECRET_KEY=django-secret-key:latest"
```
Grant the service account `roles/secretmanager.secretAccessor`. Rotate: `gcloud secrets versions add ...` + redeploy.

### 5.3 Firebase
Hosting is static-only → put Cloud Run behind it (`firebase.json` rewrites) or use Functions (`firebase functions:secrets:set GROQ_API_KEY`). Prefer Cloud Run directly unless you need Firebase Auth/Rewrites.

### 5.4 AWS
- **SSM Parameter Store** (free): `aws ssm put-parameter --name /ipl-fanzone/GROQ_API_KEY --type SecureString --value "sk_..."` → map to env vars in App Runner / ECS task definition with a scoped task role.
- **Secrets Manager** ($0.40/secret/mo): automatic rotation; ECS `secrets` field / App Runner secrets config.
- **Elastic Beanstalk**: environment properties (visible in console — OK for hobby, SSM for real secrets).

### Golden rules
1. **If `.env` was ever committed → rotate that Groq key first** (revoke at console.groq.com), scrub history with `git filter-repo`/BFG.
2. Dev/prod different keys; rotation = env update + redeploy, never a code change.
3. Don't ship secrets in Docker layers — `.dockerignore` already excludes `.env*`; use `--env-file` or platform secrets at `docker run` only.

---

## 6. Pre-deploy checklist

```bash
python manage.py test                     # 43 tests
python manage.py check --deploy           # expect only DEBUG/SECRET_KEY/cookie warnings (set in prod env)
python manage.py collectstatic --noinput
```
- [ ] `SECRET_KEY` = fresh 50-char random, `DEBUG=False`
- [ ] `ALLOWED_HOSTS` + `CSRF_TRUSTED_ORIGINS` match the public URL, `SITE_URL` set (sitemap/canonical)
- [ ] `DJANGO_SETTINGS_MODULE=ipl_platform.settings_production` on the host (HTTPS redirects, secure cookies, HSTS, file logging)
- [ ] Groq key from console + live `GROQ_MODEL`
- [ ] Optional: PostgreSQL via `DB_*` vars (SQLite survives single-instance Docker deploys fine)

## 7. Post-deploy smoke test (5 min)

```
GET  /                      200
GET  /scorecard/            200   (gold IPL chip when an IPL match is live)
WS   /ws/live/              opens & pushes live_score_update (or JS polling pill shows)
POST /jarvis/ask/ {"message":"who won ipl 2016"}   → 200, source:"offline"  (no Groq burned)
POST /jarvis/ask/ ×11 {"message":"predict ipl"}    → 11th = 429 + Retry-After
GET  /privacy/              200   (banner appears until a choice is made)
GET  /privacy/export/?username=x   → JSON attachment
POST /privacy/delete/              → {ok:true, deleted:{...}}
```

## 8. Troubleshooting

| Symptom | Cause → Fix |
|---|---|
| Jarvis gives witty fallback jokes | Groq error — check `[JARVIS ERROR]` logs & `GROQ_MODEL` is live |
| Jarvis `source:"no-key"` | `GROQ_API_KEY` unset — offline stats still answer |
| 429s too aggressive | Raise `JARVIS_RATE_PER_MINUTE` env var |
| No WS updates on Vercel | Expected — polling fallback is active by design |
| Live list shows demo data | Cricbuzz unreachable from host — cached/mock design keeps site up |
| New deploy shows old stats | `data/ipl_processed.json` is cached; RAG corpus auto-invalidates on file mtime |
