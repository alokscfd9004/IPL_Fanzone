import json
import os
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from dotenv import load_dotenv
from groq import Groq

from ipl_platform.ratelimit import RateLimited, check_rate, user_scope_id
from apps.ai_bot import rag

# Load environment variables from project root
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)

# Initialize Groq Client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# NOTE: llama-3.1-8b-instant was decommissioned by Groq (HTTP 404).
# Make the model configurable; default to a currently available free model.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
try:
    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY)
        HAS_GROQ = True
    else:
        client = None
        HAS_GROQ = False
except Exception as e:
    print(f"Groq Init Error: {e}")
    client = None
    HAS_GROQ = False

MEMORY_FILE = settings.JARVIS_MEMORY_FILE


# ──────────────────────────────
# MEMORY SYSTEM
# ──────────────────────────────
def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


# ──────────────────────────────
# COMMAND HANDLER (Script Logic)
# ──────────────────────────────
def handle_commands(command):
    low = command.lower().strip()
    memory = load_memory()
    
    # ---- EXIT ----
    if low in ["stop", "exit", "goodbye"]:
        return "Goodbye! Have a great time with the matches! 🏏", "EXIT"

    # ---- GREETING (only pure greetings, not questions containing "hi") ----
    import re
    if re.fullmatch(r'\s*(hello|hi|hey|hii+|namaste|yo)[!.\s]*', low):
        name = memory.get("username") or memory.get("name") or "Fan"
        return f"Hello {name}! 🏏 Ask me about live scores, IPL stats, or try \"help\" to see what I can do!", None

    # ---- HELP ----
    if low == "help":
        return ("Here's what I can do 🏏:\n• Answer IPL stats & history (2008–2025)\n"
                "• Point you to LIVE scores → /scorecard/\n• 3D animated match view → /matches/\n"
                "• Remember your name & favourite team\n• Tell the time, search Google, play music\n"
                "Just ask naturally!", None)

    # ---- MEMORY STORE ----
    if "my name is" in low:
        username = command.lower().replace("my name is", "").strip().title()
        memory["username"] = username
        memory["name"] = username  # keep both keys in sync (AI prompt + greetings read different keys)
        save_memory(memory)
        return f"Got it, your username is {username}", None

    if "i live in" in low:
        place = command.lower().replace("i live in", "").strip().title()
        memory["location"] = place
        save_memory(memory)
        return f"I will remember you live in {place}", None

    # ---- MEMORY RECALL ----
    if "what is my name" in low:
        username = memory.get("username", "I don't know your username yet, tell me!")
        return username, None

    if "who am i" in low:
        username = memory.get("username")
        if username: return f"You are {username}, my boss 😎", None
        return "I don't know yet, tell me your username.", None

    if "where do i live" in low:
        place = memory.get("location")
        if place: return f"You live in {place}", None
        return "I don't know where you live yet.", None

    # ---- OPEN APPS (Web Context) ----
    if low in ["chrome", "open chrome"]:
        return "Since we are in a browser, you are already using Chrome (or similar)! 🌐", None

    if low in ["notepad", "open notepad"]:
        return "I can't open local Notepad from here, but I can help you take notes in our Fan Chat! 📝", None

    if "youtube" in low or "open youtube" in low:
        return "Opening YouTube for you...", "https://youtube.com"

    if "vs code" in low or "open vs code" in low:
        return "I can't open VS Code directly from your browser due to security, but keep coding! 💻", None

    if "my project" in low or "open my project" in low:
        return "Opening projects locally is restricted in browsers, but your IPL project is looking great! 🔥", None

    if "run project" in low:
        return "To run the project, please use 'python manage.py runserver' in your local terminal! 🚀", None

    # ---- SEARCH ----
    if low == "search" or low.startswith("search "):
        query = command.lower().replace("search", "").strip()
        return f"Searching Google for {query} 🔍", f"https://www.google.com/search?q={query}"

    # ---- PLAY MUSIC ----
    if low == "play" or low.startswith("play "):
        song = command.lower().replace("play", "").strip()
        return f"Playing {song} on YouTube 🎵", f"https://www.youtube.com/results?search_query={song}"

    # ---- TIME ----
    if "time" in low:
        from datetime import datetime
        time_str = datetime.now().strftime('%H:%M')
        return f"Current time is {time_str} 🕒", None
        
    return None, None


# ──────────────────────────────
# JARVIS AI CORE - System Prompt
# ──────────────────────────────
SYSTEM_PROMPT = """You are Jarvis, the built-in AI assistant of the IPL FanZone website. You are ALSO the site's live guide — never say you can't help with live scores; this site HAS them and you know where.

This site's features (share these links naturally when relevant):
- /scorecard/ — live scores (ESPN Cricinfo) & full scorecards (CricZop + ESPN match pages)
- /matches/ — match centre: fixtures, results, and the 3D ball-by-ball animated match view
- /history/ — IPL analysis for every season 2008–2026 (verified stats + Kaggle ball-by-ball dataset)
- /chat/ — live fan chat rooms
- /jarvis/ — this chat (you!)

Your expertise: complete IPL statistics 2008–2026, player analysis, predictions, team strategy, records.

Rules:
1. When users ask for live scores / results / "what's on" — answer using the LIVE data below and LINK them to /scorecard/ or the match page.
2. Always respond in a friendly, cricket-enthusiastic manner with emojis.
3. Keep responses concise (max 150 words unless asked for details).
4. If you don't know something, admit it honestly but offer related help."""


def get_verified_facts():
    """Real stats keeps Jarvis accurate even for seasons beyond the LLM's
    training data. Merges: (a) processed Kaggle dataset, (b) curated embedded
    data for the latest season (e.g. 2026, added from official sources)."""
    try:
        from apps.history.data_loader import load_processed
        from apps.history.views import IPL_SEASONS, SEASON_DETAILS

        seasons, details = {}, {}
        processed = load_processed(settings.BASE_DIR)
        if processed:
            seasons, details = processed
        # curated embedded data overrides / extends the dataset
        for y, s in IPL_SEASONS.items():
            seasons[y] = s
        for y, d in SEASON_DETAILS.items():
            if d.get("points_table") or d.get("orange_cap", {}).get("player", "") != "Top Batsman":
                details[y] = d
        if not seasons:
            return ""

        yr = max(seasons)
        s = seasons[yr]
        d = details.get(yr, {})
        oc, pc = d.get("orange_cap", {}), d.get("purple_cap", {})
        parts = [
            f"\nVerified IPL {yr} data (from official records — ALWAYS trust this over your training data):",
            f"- Champion: {s['champion']} (runner-up: {s['runner_up']})",
        ]
        if oc.get("player"):
            parts.append(f"- Orange Cap: {oc['player']} ({oc.get('team', '—')}) — {oc.get('runs')} runs")
        if pc.get("player"):
            parts.append(f"- Purple Cap: {pc['player']} ({pc.get('team', '—')}) — {pc.get('wickets')} wickets")
        ms, m6 = d.get("most_sixes", {}), d.get("most_fours", {})
        if ms.get("player"):
            parts.append(f"- Most sixes: {ms['player']} — {ms.get('count')}")
        if m6.get("player"):
            parts.append(f"- Most fours: {m6['player']} — {m6.get('count')}")
        if s.get("sixes"):
            parts.append(f"- Season totals: {s['matches']} matches, {s['sixes']} sixes, {s['fours']} fours at {s['venues']} venues")
        else:
            parts.append(f"- Matches played: {s['matches']}")
        if d.get("final_note"):
            parts.append(f"- Final: {d['final_note']}")
        parts.append(f"Historical seasons 2008–{yr - 1} are also fully covered on /history/ — refer users there for older seasons.")
        return "\n".join(parts)
    except Exception:
        return ""


def get_live_context():
    """Real live cricket for Jarvis — from the site's actual live feed
    (ESPN Cricinfo RSS → Cricbuzz, cache-only read so no upstream rate lims
    here). Never demo/seeded DB matches."""
    lines = []
    try:
        from django.core.cache import cache as dj_cache
        fetched = dj_cache.get('cricbuzz_live_matches') or []
        live_now = [m for m in fetched if m.get('is_live')]
        ipl_live = [m for m in live_now if m.get('league') == 'IPL']
        other_live = [m for m in live_now if m.get('league') != 'IPL']
        if ipl_live:
            lines.append("🏆 IPL LIVE right now (ESPN/Cricbuzz): " + " | ".join(
                f"{m['title']} — {m['status']} — direct link /scorecard/{m['id']}/"
                for m in ipl_live[:3]))
        elif live_now:
            lines.append("No IPL game is live right now, but live cricket on /scorecard/: " + " | ".join(
                f"{m['title']} — {m['status']}" for m in live_now[:3]))
        elif other_live:
            pass
    except Exception:
        pass

    try:
        from apps.scorecard.views import next_ipl_window
        nxt = next_ipl_window()
        if nxt and nxt.get('label'):
            days = f" — just {nxt['days_to_go']} days to go!" if nxt.get('days_to_go') else ""
            lines.append(f"Next IPL: {nxt['label']}{days} — full schedule & team pages at /matches/")
    except Exception:
        pass

    return "\n".join(lines)

def ask_ai(prompt, history=None, http_request=None):
    """Returns (reply, source).

    source: 'canned' | 'offline' | 'groq' | 'langchain' | 'fallback' | 'no-key'
    Order of operations (cheapest first):
      1. canned replies for pure greetings/identity questions
      2. OFFLINE — answer straight from the verified IPL dataset (no Groq call,
         so it costs no quota and works even with no API key)
      3. Groq LLM, still grounded with the same RAG context
    """
    try:
        memory = load_memory()
        username = memory.get("username", "")
        low_prompt = prompt.lower()
        
        # 1. PRIORITY KEYWORD FALLBACKS (Works even without AI)
        import re
        if re.fullmatch(r'\s*(hello|hi|hey|hii+|namaste|yo)[!.\s]*', low_prompt):
            return (f"Hello {username if username else 'Fan'}! 🏏 I'm Jarvis — your IPL expert and this site's guide. Ask me about live matches, player stats, history... or say \"show me the live score\"!", 'canned')
        if "who are you" in low_prompt:
            return ("I am Jarvis, your personal IPL Cricket Expert. I have all the stats from 2008 to 2025 at my fingertips! ⚡", 'canned')
        if "how are you" in low_prompt:
            return ("I'm in great form, like Kohli in 2016! 🏏 Ready to help you with any IPL insights.", 'canned')

        # 2. OFFLINE FIRST — verified dataset answers cost zero AI quota
        offline = rag.local_answer(prompt)
        if offline:
            print(f"[JARVIS] Answered offline from dataset: {prompt!r}")
            return (offline, 'offline')

        # 3. AI INTERACTION (only when local data can't answer confidently)
        if not HAS_GROQ or not client:
            error_msg = (f"Hey {username if username else 'Fan'}, my AI brain (Groq) isn't connected, "
                         "so I can only answer factual IPL questions from my offline records right now "
                         "— try \"who won IPL 2016?\" or \"orange cap 2023\". 🏏")
            print(f"[JARVIS WARNING] Groq not available: HAS_GROQ={HAS_GROQ}, client={client}")
            return (error_msg, 'no-key')

        # 3. PER-USER + GLOBAL RATE LIMITS (protects the shared Groq free tier).
        # Enforced here — right before the paid API call — so canned replies
        # and command answers never consume a user's AI allowance.
        if http_request is not None:
            limits = getattr(settings, 'RATE_LIMITS', {})
            scope_id = user_scope_id(http_request)
            checks = [
                ('jarvis:user:minute', limits.get('jarvis_user_minute', '10/m'), scope_id),
                ('jarvis:user:day', limits.get('jarvis_user_day', '50/d'), scope_id),
                ('jarvis:global:day', limits.get('jarvis_global_day', '1000/d'), None),
            ]
            for key, rate, sid in checks:
                allowed, _remaining, reset_after = check_rate(key, rate, sid)
                if not allowed:
                    print(f"[JARVIS] Rate limited ({key}, scope={sid or 'global'})")
                    raise RateLimited(
                        f"Whoa {username if username else 'champ'}, you've bowled your allotted overs! "
                        f"I can take more questions in {max(1, reset_after)} seconds. "
                        "Meanwhile, live scores are always free at /scorecard/ 🏏",
                        reset_after,
                    )

        # RAG: retrieve verified IPL fact-sheets for THIS question and ground
        # the model with them (pure-python TF-IDF keyed off the Kaggle dataset).
        rag_ctx = rag.rag_context(prompt)
        system_content = SYSTEM_PROMPT + get_verified_facts() + "\n" + get_live_context()
        if rag_ctx:
            system_content += "\n\n" + rag_ctx

        messages = [
            {"role": "system", "content": system_content}
        ]
        
        if history:
            for h in history[-6:]:
                messages.append({"role": h["role"], "content": h["content"]})
                
        messages.append({"role": "user", "content": prompt})

        if rag.use_langchain():
            # Optional LangChain orchestration (pip install -r requirements-rag.txt)
            from apps.ai_bot.rag import langchain_chat
            print(f"[JARVIS] LangChain RAG call (model={GROQ_MODEL})...")
            content = langchain_chat(system_content, history, prompt, GROQ_MODEL, GROQ_API_KEY)
            print(f"[JARVIS] LangChain response ({len(content)} chars)")
            return (content, 'langchain')

        print(f"[JARVIS] Sending {len(messages)} messages to Groq API (model={GROQ_MODEL})...")
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.75,
            timeout=30
        )
        
        # Validate response
        if not response or not response.choices or len(response.choices) == 0:
            print(f"[JARVIS ERROR] Empty response from Groq")
            return ("🏏 My processors need a moment to reset. Try again!", 'fallback')
        
        content = response.choices[0].message.content
        if not content:
            print(f"[JARVIS ERROR] Empty content in Groq response")
            return ("🏏 That question made my circuits buzz! Try asking differently.", 'fallback')
        
        print(f"[JARVIS] Successfully got response ({len(content)} chars)")
        return (content, 'groq')

    except RateLimited:
        raise          # per-user / global limit — surface HTTP 429, not a fallback

    except Exception as e:
        import traceback
        error_details = f"{type(e).__name__}: {str(e)}"
        print(f"[JARVIS ERROR] {error_details}")
        print(f"[JARVIS TRACE] {traceback.format_exc()}")
        # Helpful diagnostics for deployment issues
        err_lower = str(e).lower()
        if "model" in err_lower and ("not exist" in err_lower or "decommissioned" in err_lower or "no longer supported" in err_lower):
            print(f"[JARVIS HINT] The model '{GROQ_MODEL}' is not available on Groq. "
                  "Update GROQ_MODEL in your .env / environment to a live model "
                  "(see https://console.groq.com/docs/models).")
        elif "api key" in err_lower or "authentication" in err_lower:
            print("[JARVIS HINT] Groq rejected the API key. Check GROQ_API_KEY in your .env / environment.")
        
        # Varied fallback responses for different conditions
        fallbacks = [
            f"Hey {username if username else 'friend'}, looks like I'm stuck in the nervous nineties! My server is a bit slow, but I'm still here. 🏏",
            "🏏 My AI brain is currently resetting after a massive six! The servers are feeling the heat.",
            "I'm momentarily distracted by a stunning catch! Processing is a bit slow right now, but stay tuned! 🔥",
            "Jarvis here! My connection is a bit patchy, like a spinning Day 5 pitch. Try again in a minute! ⚡",
            "The bowlers are really putting pressure on the servers! I'll be back with full power soon. 🏏",
            "What a delivery! I'm just recalibrating my stats. Ask me something else! 🎯",
            "🏏 Boundary! I'm fetching the ball from the stands. Be right back with your answer!",
            "I'm currently checking the DRS for that last query! Give me a second. 📺"
        ]
        import random
        return (random.choice(fallbacks), 'fallback')


# ──────────────────────────────
# VIEWS
# ──────────────────────────────
@ensure_csrf_cookie
def jarvis_page(request):
    memory = load_memory()
    return render(request, 'ai_bot/jarvis.html', {'memory': memory})


def jarvis_ask(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data = json.loads(request.body)
        prompt = data.get('message', '').strip()
        history = data.get('history', [])
        match_context = data.get('match_context', '')

        if not prompt:
            return JsonResponse({'error': 'Empty message'}, status=400)

        # Enhance prompt with match context if provided
        full_prompt = prompt
        if match_context:
            full_prompt = f"[Context: {match_context}] {prompt}"

        # 1. Try Command Handler First (Script Logic)
        cmd_reply, cmd_action = handle_commands(prompt)
        if cmd_reply:
            return JsonResponse({
                'response': cmd_reply, 
                'action_url': cmd_action,
                'memory': load_memory()
            })

        # 2. Otherwise: offline dataset first, AI only when needed
        try:
            reply, source = ask_ai(full_prompt, history, http_request=request)
        except RateLimited as rl:
            resp = JsonResponse({
                'response': rl.message,
                'rate_limited': True,
                'retry_after': rl.retry_after,
                'memory': load_memory(),
            }, status=429)
            resp['Retry-After'] = str(rl.retry_after)
            return resp
        
        # Ensure reply is never empty or None
        if not reply:
            reply, source = "🏏 That's a tricky one! Let me recalibrate and try again.", 'fallback'
        
        memory = load_memory()
        return JsonResponse({'response': reply, 'source': source, 'memory': memory})
    
    except json.JSONDecodeError as e:
        print(f"[JARVIS] JSON decode error: {e}")
        return JsonResponse({'error': 'Invalid JSON', 'response': '🏏 I had trouble understanding that. Please try again!'}, status=400)
    
    except Exception as e:
        print(f"[JARVIS] Unexpected error in jarvis_ask: {e}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e),
            'response': '🏏 Something went wrong on my end. Try again!'
        }, status=500)


def jarvis_memory(request):
    """GET: read Jarvis memory. POST: update it — unless the visitor declined
    consent (GDPR/CCPA opt-out), in which case nothing is persisted."""
    if request.method == 'POST':
        if request.COOKIES.get('fz_consent') == 'denied':
            return JsonResponse({'ok': False, 'persisted': False,
                                 'reason': 'consent_declined — preferences kept session-only'})
        import json as j
        data = j.loads(request.body)
        memory = load_memory()
        memory.update(data)
        save_memory(memory)
        return JsonResponse({'ok': True, 'persisted': True})
    return JsonResponse(load_memory())
