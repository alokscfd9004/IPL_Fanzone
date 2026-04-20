# 🏏 IPL FanZone v2 — Complete Full-Stack Platform

Matches the IPL Analysis dashboard screenshot with live data, Cricbuzz scraping, Groq AI (Jarvis), and 3D match animation.

---

## ⚡ QUICK START (3 commands)

```bash
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo
python manage.py runserver
```
Open → http://127.0.0.1:8000

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
│   │   └── urls.py               # Matches the screenshot EXACTLY
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
| `/jarvis/` | **Jarvis AI chat** (Groq Llama 3.1 + memory) |

---

## ✨ FEATURES

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
- Crictimes iframe always shows real live scores

### Live Score Widget (always works!)
```html
<iframe src="https://bwidget.crictimes.org/" 
        style="width:100%;min-height:250px;" 
        frameborder="0" scrolling="yes"></iframe>
```
Embedded on: Home, Match Detail, History, Scorecard pages

---

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
groq>=0.4.0          — Groq Llama 3.1 AI
beautifulsoup4       — Cricbuzz scraping
lxml                 — HTML parser
requests             — HTTP calls
python-dotenv        — .env support
Chart.js (CDN)       — Trend charts
```
