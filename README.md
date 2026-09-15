# 🏏 IPL FanZone v2 — Complete Full-Stack Platform

IPL fan hub with live data (free CricketData.org widgets + Cricbuzz scraping), Groq AI (Jarvis), 3D match animation, and 18 seasons of real Kaggle IPL data.

---

## ⚡ QUICK START (4 commands)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py process_ipl_data   # optional: real 2008–2025 Kaggle stats
python manage.py runserver
```
Open → http://127.0.0.1:8000

> **.env format matters!** Use `KEY=value` (equals sign), e.g.:
> ```
> GROQ_API_KEY=gsk_your_key
> GROQ_MODEL=openai/gpt-oss-20b
> ```
> Groq decommissions old models (e.g. `llama-3.1-8b-instant` is gone) — if Jarvis replies with fallback jokes instead of real answers, check your server logs and pick a live model from https://console.groq.com/docs/models

---



---


## 📁 PROJECT STRUCTURE

```
ipl_v2/
├── .env                          # API keys
├── requirements.txt
├── manage.py
│
├── ipl_platform/
│   ├── settings.py               # All config + API keys
│   ├── urls.py                   # Root URLs
│   └── asgi.py                   # WebSocket config
│
├── apps/
│   ├── matches/                  # 🏏 Live matches + 3D animation
│   │   ├── models.py             # Team, Match, Reaction
│   │   ├── views.py              # Home, detail, API, reactions
│   │   └── urls.py
│   │
│   ├── history/                  # 📈 IPL Analysis 2008-2025
│   │   ├── views.py              # Season data, charts, points table
│   │   ├── data_loader.py        # Kaggle dataset → JSON pipeline
│   │   └── management/commands/process_ipl_data.py
│   │
│   ├── scorecard/                # 📊 Cricbuzz scraper + live embed
│   │   ├── views.py              # BS4 scraping + Crictimes iframe
│   │   └── urls.py
│   │
│   ├── ai_bot/                   # 🤖 Jarvis AI (llama-3.1-8b-instant)
│   │   ├── views.py              # ask_ai() + memory system
│   │   └── urls.py
│   │
│   ├── chat/                     # 💬 Fan chat (WebSocket)
│   └── fans/                     # 👥 Fan profiles
│
└── templates/
    ├── base/base.html            # IPL-themed master layout with sidebar
    ├── matches/
    │   ├── home.html             # Hero + live widget + match cards
    │   ├── match_detail.html     # 3D canvas + scorecard + reactions
    │   └── all_matches.html
    ├── history/history.html      # ← MATCHES SCREENSHOT EXACTLY
    ├── scorecard/
    │   ├── scorecard.html        # Cricbuzz scrape + Crictimes embed
    │   └── scorecard_detail.html # Full batting/bowling scorecard
    └── ai_bot/jarvis.html        # Jarvis chat UI with memory panel
```

---

## 🌐 PAGES

| URL | Description |
|-----|-------------|
| `/` | Home — hero, live widget, match cards |
| `/matches/` | All IPL 2025 matches |
| `/match/<id>/` | **3D Live Animation** + reactions + Jarvis |
| `/history/?season=2025` | **IPL Analysis** — matches the screenshot! |
| `/history/?season=2008` | Historical season (2008–2024 all included) |
| `/scorecard/` | Cricbuzz scrape + Crictimes live widget |
| `/scorecard/<id>/` | Full batting scorecard |
| `/jarvis/` | **Jarvis AI chat** (offline answers + Groq RAG + source badges) |
| `/privacy/` | Privacy policy (GDPR + CCPA) |
| `/privacy/my-data/` | Export / delete your data (GDPR Art. 15/17, CCPA) |

---

## ✨ FEATURES

### 🤖 Jarvis AI — offline-first + RAG + per-user rate limits
Answer pipeline (cheapest first):
1. **Canned replies** for greetings/commands — free.
2. **Offline dataset answers** (`apps/ai_bot/rag.py`) — "who won IPL 2016?", "orange cap 2023", "list all champions" come straight from the verified ball-by-ball dataset. Zero Groq quota, works even with no API key.
3. **Groq LLM** only for open-ended questions/predictions — still grounded with RAG context.
- **RAG**: pure-Python TF-IDF retrieval over 24 auto-built fact sheets (no sklearn/numpy → deploys anywhere). Optional LangChain orchestration: `pip install -r requirements-rag.txt` + `USE_LANGCHAIN_RAG=true`.
- **Per-user + global limits**: 10 AI calls/min, 50/day per visitor (anonymous session id), plus a 1000/day site-wide cap protecting the shared free key. 429 → chat UI shows a countdown; configurable via `JARVIS_RATE_PER_*` env vars in `settings.RATE_LIMITS`.
- **Fine-tune dataset** (optional): `python manage.py build_finetune_dataset` → `data/finetune_ipl.jsonl` (~250 verified chat-format pairs).

### 🔒 GDPR / CCPA privacy (`/privacy/`)
- Cookie-consent banner; declining = no localStorage fan profile, no Jarvis memory persistence, third-party live widgets blocked until accepted.
- **Privacy policy** at `/privacy/` + **My Data** page at `/privacy/my-data/`.
- **Right to access/portability**: `GET /privacy/export/?username=…` → JSON download (chat messages, reactions, fan insights, fan profile, Jarvis memory & conversations).
- **Right to erasure**: `POST /privacy/delete/` → wipes server records + session; client drops localStorage + cookies.
- Consent API: `POST /privacy/consent/` sets `fz_consent` (180d, SameSite=Lax).

### 📡 Real-time live scores (WebSocket + fallback)
- Push channel: `ws://host/ws/live/` (`LiveScoreConsumer`), broadcasts the moment a fresh scrape lands; clients dedupe identical payloads.
- Client (`static/js/live.js`) **falls back to polling** `/scorecard/api/live/` on serverless hosts without WebSockets.
- IPL-first feed: no live IPL game? Show whatever cricket is live. When an IPL match appears it's sorted top and flagged with a gold **IPL** chip; the page pill switches to 🏏 IPL LIVE.

### 🚦 API rate limiting (`ipl_platform/ratelimit.py`)
Pure cache-framework decorator (no Redis needed — locmem by default, Redis via `CACHE_BACKEND` env). Live-score JSON APIs: 30/min per user. Fails open if the cache backend is down.

### 📈 IPL Analysis Page (matches screenshot)
- **Left sidebar**: Year display, nav links, social links
- **Champion + Runner-Up** banner
- **7 stat boxes**: Sixes, Fours, Matches, Teams, 50s, 100s, Venues
- **Orange Cap + Purple Cap** player cards with stats
- **Most 4s + Most 6s** player cards
- **Full Points Table** with team logos, NR, Tie columns
- **Season selector** dropdown — switch any year 2008-2025
- **Trend chart** (Chart.js) — sixes/fours/matches over 18 seasons
- **Crictimes live widget** embedded

### 🏟️ 3D Match Animation
- Full oval cricket ground with mowing stripes
- Pitch, stumps, crease lines, 30-yard circle
- Animated floodlights with light beam effect
- 100 crowd dots with wave animation
- Ball trajectory physics with shadow
- Particle burst: gold sparks (SIX), green (FOUR), red explosion (WICKET)
- Floating score HUD on canvas
- Auto demo mode + live API polling every 12s

### 🤖 Jarvis AI (Groq + Memory)
```python
def ask_ai(prompt):
    memory = load_memory()          # Loads name, fav_team from JSON
    name = memory.get("name", "")
    system_prompt = f"You are Jarvis, IPL expert. User: {name}..."
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant", ...)
```
- Persistent memory (`jarvis_memory.json`)
- Auto-extracts user name from conversation
- 8-message conversation history maintained
- Memory panel in sidebar shows what Jarvis knows
- Clear memory button

### 📊 Cricbuzz Scraper
- Scrapes `cricbuzz.com/cricket-match/live-scores`
- Parses match titles, scores, live status
- Scrapes full batting scorecards
- Graceful fallback to mock data

### 📈 Kaggle IPL Dataset (real stats!)
- `python manage.py process_ipl_data` downloads the public dataset (no key needed)
- Computes real per-season stats from 278k+ deliveries: champions, Orange/Purple caps, sixes/fours, 50s/100s, points tables
- Cached to `data/ipl_processed.json` — also injected into Jarvis's system prompt so the AI gives verified answers
- Embedded fallback data keeps the site working without it

### Live Score Widgets (free, no API key!)
```html
<script src="https://cdorgapi.b-cdn.net/widgets/matchlist.js"></script>   <!-- 400x300 tabs -->
<script src="https://cdorgapi.b-cdn.net/widgets/vmatchlist.js"></script>  <!-- 250x600 vertical -->
<script src="https://cdorgapi.b-cdn.net/widgets/score.js"></script>       <!-- 300x300 scrolling -->
```
Embedded on: Home, Match Detail, History, Scorecard pages

---

## 🆓 FREE DEPLOYMENT (the honest picture)

Nothing is truly "free & unlimited", but these are the best free tiers for this stack
(Django + ASGI/WebSockets + SQLite → any Docker host works):

| Platform | Always-free? | WebSockets? | Catch |
|---|---|---|---|
| **Render** | ✅ Free Web Service | ✅ | Sleeps after 15 min idle (cold start ~30s), 750 h/mo |
| **Fly.io** | ✅ Free allowance | ✅ | Shared CPU, 256 MB RAM |
| **Hugging Face Spaces** | ✅ | ✅ | Public repo/space by default |
| **Vercel** | ✅ generous | ❌ no WS, read-only FS | Chat/WS features off, polling fallback kicks in |
| **Oracle Cloud "Always Free"** | ✅ biggest free VM | ✅ | You manage the VM yourself |

**Everything needed to stay inside free tiers is built in:**
- Groq free key protected by per-user (10/min, 50/day) + global (1000/day) limits
- Cricbuzz scraping capped at 1 fetch/90s + 30-min cache → no IP bans
- SQLite DB, WhiteNoise static files, InMemory channels layer — no paid services
- Env-only secrets (`.env` never committed)

Docker one-liner for Render/Fly/HF Spaces:

```bash
docker build -f dockerfile -t ipl-fanzone . && docker run -p 8080:8080 --env-file .env ipl-fanzone
```

## 🚀 PRODUCTION

```bash
# With WebSockets
pip install daphne
daphne -b 0.0.0.0 -p 8000 ipl_platform.asgi:application

# With Redis channel layer (for multi-worker)
pip install channels-redis
# Update settings.py CHANNEL_LAYERS to use Redis
```

---

## 📦 DEPENDENCIES

```
Django>=4.2          — Web framework
channels>=4.0        — WebSocket support
daphne               — ASGI server (production)
groq>=1.0            — Groq AI (model via GROQ_MODEL env)
beautifulsoup4 + lxml — Cricbuzz scraping
requests             — HTTP calls
python-dotenv        — .env support
kagglehub + pandas   — IPL dataset processing
Chart.js (CDN)       — Trend charts
```
