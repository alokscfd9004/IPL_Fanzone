import json
import os
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from dotenv import load_dotenv
from groq import Groq

# Load environment variables from project root
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)

# Initialize Groq Client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
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

    # ---- GREETING ----
    if "hello" in low or "hi " in low or low == "hi":
        name = memory.get("name", "there")
        return f"Hello {name}, how can I help you today? 🏏", None

    # ---- MEMORY STORE ----
    if "my name is" in low:
        username = command.lower().replace("my name is", "").strip().title()
        memory["username"] = username
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
SYSTEM_PROMPT = """You are Jarvis, an intelligent IPL Cricket Expert AI Assistant. Your expertise includes:
- Complete IPL statistics from 2008 to 2025
- Player performance analysis and comparisons
- Match predictions and insights
- Team strategies and records
- Historical facts and memorable moments

Always respond in a friendly, cricket-enthusiastic manner. Use cricket emojis and metaphors when appropriate. 
Provide accurate information about IPL records, player stats, and match details.
If you don't know something, admit it honestly but try to provide related helpful information.
Keep responses concise but informative (max 150 words unless asked for details)."""

def ask_ai(prompt, history=None):
    try:
        memory = load_memory()
        username = memory.get("username", "")
        low_prompt = prompt.lower()
        
        # 1. PRIORITY KEYWORD FALLBACKS (Works even without AI)
        if "hello" in low_prompt or "hi" in low_prompt:
            return f"Hello {username if username else 'Fan'}! 🏏 I'm Jarvis. Ready to talk some IPL? What's on your mind?"
        if "who are you" in low_prompt:
            return "I am Jarvis, your personal IPL Cricket Expert. I have all the stats from 2008 to 2025 at my fingertips! ⚡"
        if "how are you" in low_prompt:
            return "I'm in great form, like Kohli in 2016! 🏏 Ready to help you with any IPL insights."
        
        # 2. AI INTERACTION
        if not HAS_GROQ or not client:
            error_msg = f"Hey {username if username else 'Fan'}, my AI brain (Groq) isn't connected right now. Please check the .env file for the GROQ_API_KEY! 🏏"
            print(f"[JARVIS WARNING] Groq not available: HAS_GROQ={HAS_GROQ}, client={client}")
            return error_msg

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        if history:
            for h in history[-6:]:
                messages.append({"role": h["role"], "content": h["content"]})
                
        messages.append({"role": "user", "content": prompt})

        print(f"[JARVIS] Sending {len(messages)} messages to Groq API...")
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=500,
            temperature=0.75,
            timeout=30
        )
        
        # Validate response
        if not response or not response.choices or len(response.choices) == 0:
            print(f"[JARVIS ERROR] Empty response from Groq")
            return "🏏 My processors need a moment to reset. Try again!"
        
        content = response.choices[0].message.content
        if not content:
            print(f"[JARVIS ERROR] Empty content in Groq response")
            return "🏏 That question made my circuits buzz! Try asking differently."
        
        print(f"[JARVIS] Successfully got response ({len(content)} chars)")
        return content

    except Exception as e:
        import traceback
        error_details = f"{type(e).__name__}: {str(e)}"
        print(f"[JARVIS ERROR] {error_details}")
        print(f"[JARVIS TRACE] {traceback.format_exc()}")
        
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
        return random.choice(fallbacks)


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

        # 2. Otherwise use AI
        reply = ask_ai(full_prompt, history)
        
        # Ensure reply is never empty or None
        if not reply:
            reply = "🏏 That's a tricky one! Let me recalibrate and try again."
        
        memory = load_memory()
        return JsonResponse({'response': reply, 'memory': memory})
    
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
    if request.method == 'POST':
        import json as j
        data = j.loads(request.body)
        memory = load_memory()
        memory.update(data)
        save_memory(memory)
        return JsonResponse({'ok': True})
    return JsonResponse(load_memory())
